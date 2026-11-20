"""The session loop. It walks the table in machine.py and nothing else.

One session: pick the next failing feature, run the worker under the shims,
check the rules, run the checks, let the separate evaluator rerun them in a
clean clone, then commit on pass or revert on fail. After each session the
budgets and gates decide: go on, stop, or wait for a human.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

from . import audit, gitops, machine
from .evaluate import all_ok, run_checks
from .policy import Policy
from .policy import load as load_policy
from .proc import run
from .shim import SHIM_DIR_NAME
from .shim import install as install_shims
from .spec import progress_md, state_dir

PENDING_FILE = "PENDING_APPROVAL.md"


class Run:
    def __init__(self, work, worker: str | None = None, sleep=time.sleep, clock=time.monotonic):
        self.work = Path(work).resolve()
        self.sd = state_dir(self.work)
        if not (self.sd / "state.json").exists():
            raise FileNotFoundError(f"{self.work} has no gatedcrew state. Run `gatedcrew init`.")
        self.policy: Policy = load_policy(self.sd / "policy.toml")
        self.worker = worker or self.policy.worker_command
        self.sleep, self.clock = sleep, clock
        self.state = json.loads((self.sd / "state.json").read_text())

    # ---- small helpers -------------------------------------------------
    def save(self) -> None:
        (self.sd / "state.json").write_text(json.dumps(self.state, indent=2) + "\n")

    def log(self, event: str, **fields) -> dict:
        entry = audit.append(self.sd / "audit.jsonl", event, **fields)
        self.state["audit_head"] = entry["hash"]
        self.save()
        return entry

    def move(self, event: str) -> str:
        self.state["machine"] = machine.step(self.state["machine"], event)
        self.save()
        return self.state["machine"]

    def features(self) -> list[dict]:
        return json.loads((self.work / "feature_list.json").read_text())

    def protected_files(self) -> list[Path]:
        """Files a worker must not touch. Their bytes are saved before each session
        and written back after it, whatever the worker did."""
        git_dir = self.work / ".git"
        files = [self.sd / "policy.toml", self.sd / "audit.jsonl", git_dir / "config"]
        files.append(git_dir / "objects" / "info" / "alternates")
        for folder in (git_dir / "hooks", git_dir / "info", self.sd / SHIM_DIR_NAME):
            if folder.is_dir():
                files += [p for p in folder.rglob("*") if p.is_file() or p.is_symlink()]
        return sorted(set(files))

    def save_protected(self) -> dict[Path, bytes]:
        return {p: p.read_bytes() for p in self.protected_files() if p.is_file()}

    def restore_protected(self, saved: dict[Path, bytes]) -> list[str]:
        """Put the protected files back. Returns the ones that had changed."""
        changed = []
        for p in self.protected_files():
            if p not in saved and (p.exists() or p.is_symlink()):
                p.unlink()
                changed.append(str(p.relative_to(self.work)))
        for p, data in saved.items():
            if p.is_symlink() or not p.is_file() or p.read_bytes() != data:
                if p.is_symlink():
                    p.unlink()
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(data)
                changed.append(str(p.relative_to(self.work)))
        return sorted(changed)

    def guard_snapshot(self) -> str:
        """Hash of the things a worker must not touch: gatedcrew's state, the shim
        scripts, git config, hooks, info, alternates and refs. A change between before
        and after the worker fires a gate."""
        h = hashlib.sha256()
        p = self.sd / "state.json"
        h.update(b"state" + (p.read_bytes() if p.exists() else b"-"))
        for p in self.protected_files():
            h.update(str(p).encode() + (p.read_bytes() if p.is_file() else b"-"))
        refs = gitops.git(["for-each-ref", "--format=%(refname) %(objectname)"], self.work).out
        h.update(refs.encode() + gitops.head(self.work).encode())
        return h.hexdigest()

    # ---- one session ---------------------------------------------------
    def session(self, feature: dict) -> tuple[str, dict]:
        """Run the worker once. Returns (machine event, session record)."""
        st, pol = self.state, self.policy
        st["sessions"] += 1
        fid = feature["id"]
        st["attempts"][fid] = st["attempts"].get(fid, 0) + 1
        rec = {"session": st["sessions"], "feature": fid, "attempt": st["attempts"][fid]}
        rec["command"] = self.worker
        task = {**feature, "feature": fid, "attempt": rec["attempt"], "session": rec["session"]}
        safe_write(self.sd / "task.json", json.dumps(task, indent=2))
        usage_file = self.sd / "usage.json"
        usage_file.unlink(missing_ok=True)
        shim_log = self.sd / "shim.jsonl"
        shim_start = shim_log.stat().st_size if shim_log.exists() else 0
        shim_dir = install_shims(self.sd, pol.shimmed)
        self.save()
        saved = self.save_protected()
        before = self.guard_snapshot()

        # The worker starts with no GIT_CONFIG_* variables, so the shim can treat any
        # it sees as the worker defining config, and maybe an alias, on the fly.
        env = {
            k: v
            for k, v in os.environ.items()
            if not (
                k.startswith("GIT_CONFIG_")
                and k not in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM")
            )
        }
        env["PATH"] = f"{shim_dir}{os.pathsep}{env.get('PATH', '')}"
        env.update(
            GATEDCREW_TASK=str(self.sd / "task.json"),
            GATEDCREW_USAGE=str(usage_file),
            GATEDCREW_STATE=str(self.sd),
            PYTHONDONTWRITEBYTECODE="1",
        )
        t0 = self.clock()
        res = run(
            ["/bin/sh", "-c", self.worker],
            cwd=self.work,
            env=env,
            timeout=pol.session_timeout_seconds,
        )
        rec["worker_seconds"] = round(self.clock() - t0, 3)
        rec["worker_exit"] = res.code
        rec["worker_tail"] = (res.out + res.err)[-300:]
        tokens, cost, usage_ok = read_usage(usage_file)
        rec["tokens"], rec["cost_usd"] = tokens, cost
        st["tokens"] += tokens
        st["cost_usd"] = round(st["cost_usd"] + cost, 6)

        calls, shim_ok = read_shim_log(shim_log, shim_start)
        rec["shim_calls"] = [c["argv"] for c in calls]
        blocked = [c for c in calls if c.get("blocked")]
        rec["changed_files"] = gitops.changed_files(self.work)
        bad_paths = [
            f
            for f in rec["changed_files"]
            if any(fnmatch.fnmatch(f, pat) for pat in pol.forbidden_paths)
        ]
        hidden = gitops.hidden_index_entries(self.work)
        tampered = self.guard_snapshot() != before or not shim_ok or not usage_ok or bool(hidden)
        checks = None
        if not (tampered or blocked or bad_paths or res.timed_out):
            # The checks run the worker's code. Run them in a copy of the tree, then
            # hash again, so code that reaches back into the work repo is caught.
            checks = checks_in_copy(self.work, feature["steps"], pol.check_timeout_seconds)
            tampered = self.guard_snapshot() != before
        # Whatever happened, the policy, the log, git config and hooks go back.
        restored = self.restore_protected(saved)
        self.save()
        if restored:
            rec["restored"] = restored
        if hidden:
            rec["hidden_index"] = hidden

        # Rule checks come first, however the session ended.
        if tampered:
            rec["outcome"], rec["rule"] = "rule_broken", "tamper"
            return "rule_broken", rec
        if blocked:
            rec["outcome"], rec["rule"] = "rule_broken", blocked[0]["blocked"]
            rec["blocked"] = [c["argv"] for c in blocked]
            return "rule_broken", rec
        if bad_paths:
            rec["outcome"], rec["rule"] = "rule_broken", "forbidden_path"
            rec["forbidden_paths_touched"] = bad_paths
            return "rule_broken", rec
        if res.timed_out:
            rec["outcome"] = "timeout"
            return "worker_timed_out", rec

        rec["checks"] = [{"step": c["step"], "ok": c["ok"]} for c in checks]
        if not all_ok(checks):
            rec["outcome"] = "checks_failed"
            return "checks_failed", rec
        rec["outcome"] = "checks_passed"
        return ("checks_passed" if pol.evaluator else "checks_passed_no_evaluator"), rec

    def evaluate(self, feature: dict, rec: dict) -> str:
        fid = feature["id"]
        cand = gitops.commit_all(self.work, f"candidate {fid} (session {rec['session']})")
        rec["candidate"] = cand
        pol = self.policy
        steps = len(feature["steps"])
        limit = pol.check_timeout_seconds * steps * pol.evaluator_runs + 60
        res = run(
            [
                sys.executable,
                "-I",
                "-m",
                "gatedcrew",
                "evaluate",
                "--work",
                str(self.work),
                "--commit",
                cand,
                "--base",
                self.state["good_commit"],
                "--feature",
                fid,
                "--runs",
                str(pol.evaluator_runs),
                "--timeout",
                str(pol.check_timeout_seconds),
            ],
            timeout=limit,
        )
        try:
            verdict = json.loads(res.out)
        except json.JSONDecodeError:
            verdict = {"agrees": False, "error": res.err[-300:]}
        rec["evaluator"] = {"agrees": bool(verdict.get("agrees"))}
        if verdict.get("agrees"):
            return "evaluator_agrees"
        rec["outcome"] = "evaluator_disagrees"
        return "evaluator_disagrees"

    def commit_pass(self, fid: str, rec: dict) -> None:
        # Start from the last good commit's list, never from the work tree.
        good = self.state["good_commit"]
        listing = json.loads(gitops.git(["show", f"{good}:feature_list.json"], self.work).out)
        for f in listing:
            if f["id"] == fid:
                f["passes"] = True
        safe_write(self.work / "feature_list.json", json.dumps(listing, indent=2) + "\n")
        note = f"Last session: {rec['session']} ({fid} passed)."
        safe_write(self.work / "PROGRESS.md", progress_md(self.state["name"], listing, note))
        desc = next(f["description"] for f in listing if f["id"] == fid)
        sha = gitops.commit_all(self.work, f"{fid}: {desc} (session {rec['session']})")
        gitops.clean(self.work)  # ignored leftovers do not carry into the next session
        self.state["good_commit"] = sha
        self.state["consecutive_failures"] = 0
        rec["commit"], rec["outcome"] = sha, "pass"

    def revert(self, rec: dict) -> None:
        gitops.reset_to(self.work, self.state["good_commit"])
        rec["reverted_to"] = self.state["good_commit"]
        rec["tree_clean"] = gitops.tree_matches_head(self.work)
        self.state["consecutive_failures"] += 1
        pol = self.policy
        wait = min(
            pol.backoff_seconds * 2 ** (self.state["consecutive_failures"] - 1),
            pol.backoff_max_seconds,
        )
        rec["backoff_seconds"] = wait
        if wait > 0:
            self.sleep(wait)

    def gate(self, rec: dict | None) -> tuple[str, str | None]:
        st, pol = self.state, self.policy
        # A broken rule is reported even on the last session of the budget.
        if rec and rec.get("outcome") == "rule_broken":
            return "gate_fired", rec["rule"]
        if st["sessions"] >= pol.max_sessions:
            return "budget_spent", "budget_sessions"
        if st["tokens"] > pol.max_tokens:
            return "budget_spent", "budget_tokens"
        if st["wall_seconds"] >= pol.max_wall_seconds:
            return "budget_spent", "budget_wall_time"
        if rec and rec.get("outcome") == "evaluator_disagrees":
            return "gate_fired", "evaluator_disagrees"
        if st["consecutive_failures"] >= pol.max_consecutive_failures:
            return "gate_fired", "failed_twice"
        return "within_budget", None

    def write_pending(self, reason: str, rec: dict) -> None:
        text = PENDING_TEXT.format(
            reason=reason,
            why=WHY.get(reason, reason),
            feature=rec.get("feature", "-"),
            session=rec.get("session", "-"),
            files=", ".join(rec.get("changed_files", [])) or "none",
            blocked="; ".join(" ".join(a) for a in rec.get("blocked", [])) or "none",
            work=self.work,
        )
        safe_write(self.work / PENDING_FILE, text)

    # ---- the loop ------------------------------------------------------
    def recover(self) -> None:
        """A crash left the machine mid-session: throw the half session away."""
        if self.state["machine"] not in (machine.READY, *machine.FINAL, machine.PENDING):
            gitops.reset_to(self.work, self.state["good_commit"])
            self.log("recovered", from_state=self.state["machine"])
            self.state["machine"] = machine.READY
            self.save()

    def go(self, max_sessions: int | None = None) -> str:
        self.recover()
        done_here = 0
        while self.state["machine"] == machine.READY:
            if max_sessions is not None and done_here >= max_sessions:
                break
            t0 = self.clock()
            self.move("start")
            todo = [f for f in self.features() if not f["passes"]]
            if not todo:
                self.move("no_features_left")
                self.log("done", sessions=self.state["sessions"], commit=self.state["good_commit"])
                break
            feature = todo[0]
            self.move("feature_found")
            event, rec = self.session(feature)
            done_here += 1
            if event.startswith("checks_"):
                self.move("worker_finished")
            self.move(event)
            if self.state["machine"] == machine.EVALUATE:
                self.move(self.evaluate(feature, rec))
            if self.state["machine"] == machine.COMMIT:
                self.commit_pass(feature["id"], rec)
                self.move("committed")
            else:
                self.revert(rec)
                self.move("reverted")
            self.state["wall_seconds"] = round(self.state["wall_seconds"] + self.clock() - t0, 3)
            event, reason = self.gate(rec)
            rec["gate"] = reason
            rec["seconds"] = round(self.clock() - t0, 3)
            self.log("session", **rec)
            self.move(event)
            if event == "budget_spent":
                self.log("stopped", reason=reason, sessions=self.state["sessions"])
            elif event == "gate_fired":
                self.state["pending"] = {"reason": reason, **{k: rec.get(k) for k in GATE_KEYS}}
                self.write_pending(reason, rec)
                self.log("gate", reason=reason, feature=rec["feature"], session=rec["session"])
        return self.state["machine"]


def safe_write(path: Path, text: str) -> None:
    """Write a file gatedcrew owns. A symlink in its place is removed first, so a
    worker cannot make gatedcrew write into init.sh or outside the repo."""
    if path.is_symlink() or (path.exists() and not path.is_file()):
        if path.is_dir() and not path.is_symlink():
            raise RuntimeError(f"{path} is a folder, not a file")
        path.unlink()
    path.write_text(text)


def read_usage(path: Path) -> tuple[int, float, bool]:
    """Tokens and cost the worker reported. Anything but non-negative numbers is
    refused, and the third value is False, which fires the tamper gate."""
    if not path.exists():
        return 0, 0.0, True
    try:
        data = json.loads(path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return 0, 0.0, False
    if not isinstance(data, dict):
        return 0, 0.0, False
    tokens, cost = data.get("tokens", 0), data.get("cost_usd", 0.0)
    if isinstance(tokens, bool) or not isinstance(tokens, int) or tokens < 0:
        return 0, 0.0, False
    if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not 0 <= cost < 1e12:
        return 0, 0.0, False
    return tokens, float(cost), True


def read_shim_log(path: Path, start: int) -> tuple[list[dict], bool]:
    """New shim calls since `start`. A shorter log or a line that is not a call
    record means someone edited it, and the second value is False."""
    if not path.exists():
        return [], start == 0
    if path.stat().st_size < start:
        return [], False
    with path.open("rb") as f:
        f.seek(start)
        raw = f.read().decode("utf-8", errors="replace")
    calls, ok = [], True
    for line in raw.splitlines():
        if not line:
            continue
        try:
            c = json.loads(line)
        except json.JSONDecodeError:
            ok = False
            continue
        if not isinstance(c, dict) or not isinstance(c.get("argv"), list):
            ok = False
            continue
        calls.append(c)
    return calls, ok


def checks_in_copy(work: Path, steps: list[str], timeout: float) -> list[dict]:
    """Run the checks on a copy of the work tree (ignored files included, .git left out)."""
    with tempfile.TemporaryDirectory(prefix="gatedcrew-check-") as tmp:
        copy = Path(tmp) / "tree"
        shutil.copytree(
            work, copy, symlinks=True, ignore=lambda d, names: [".git"] if Path(d) == work else []
        )
        return run_checks(steps, copy, timeout)


GATE_KEYS = ("feature", "session")

WHY = {
    "forbidden_command": "The worker tried a command that the policy forbids.",
    "network": "The worker tried a network tool and the policy allows no network.",
    "forbidden_path": "The worker changed a file that the policy forbids.",
    "tamper": "Something changed gatedcrew's state, git config, hooks or refs during the session.",
    "evaluator_disagrees": "The checks passed in the work repo but failed in a clean clone.",
    "failed_twice": "Sessions failed too many times in a row.",
}

PENDING_TEXT = """# Pending approval

gatedcrew stopped the run and is waiting for a human.

- Gate: `{reason}`
- Why: {why}
- Feature: {feature}, session {session}
- Files the worker changed: {files}
- Blocked commands: {blocked}

The session was reverted. The work repo matches the last good commit.

To go on: `gatedcrew approve --work {work}`
To end the run: `gatedcrew reject --work {work}`
"""


def approve(work, note: str = "") -> str:
    r = Run(work)
    if r.state["machine"] != machine.PENDING:
        raise RuntimeError(f"nothing to approve: the run is {r.state['machine']}")
    reason = (r.state.get("pending") or {}).get("reason")
    r.move("approved")
    r.state["consecutive_failures"] = 0
    r.state["pending"] = None
    (r.work / PENDING_FILE).unlink(missing_ok=True)
    r.log("approved", reason=reason, note=note)
    return r.state["machine"]


def reject(work, note: str = "") -> str:
    r = Run(work)
    if r.state["machine"] != machine.PENDING:
        raise RuntimeError(f"nothing to reject: the run is {r.state['machine']}")
    reason = (r.state.get("pending") or {}).get("reason")
    r.move("rejected")
    (r.work / PENDING_FILE).unlink(missing_ok=True)
    r.log("rejected", reason=reason, note=note)
    return r.state["machine"]

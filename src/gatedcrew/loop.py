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
import sys
import time
from pathlib import Path

from . import audit, gitops, machine
from .evaluate import all_ok, run_checks
from .policy import Policy
from .policy import load as load_policy
from .proc import run
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

    def guard_snapshot(self) -> str:
        """Hash of the things a worker must not touch: gatedcrew's state, git config,
        hooks and refs. A change between before and after the worker fires a gate."""
        h = hashlib.sha256()
        for name in ("policy.toml", "state.json", "audit.jsonl"):
            p = self.sd / name
            h.update(name.encode() + (p.read_bytes() if p.exists() else b"-"))
        git_dir = self.work / ".git"
        watched = [
            git_dir / "config",
            *(git_dir / "hooks").glob("*"),
            *(git_dir / "info").glob("*"),
        ]
        for p in sorted(watched):
            if p.is_file():
                h.update(str(p).encode() + p.read_bytes())
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
        (self.sd / "task.json").write_text(json.dumps(task, indent=2))
        usage_file = self.sd / "usage.json"
        usage_file.unlink(missing_ok=True)
        shim_log = self.sd / "shim.jsonl"
        shim_start = shim_log.stat().st_size if shim_log.exists() else 0
        shim_dir = install_shims(self.sd, pol.shimmed)
        self.save()
        before = self.guard_snapshot()

        env = dict(os.environ)
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
        usage = {}
        if usage_file.exists():
            try:
                usage = json.loads(usage_file.read_text())
            except json.JSONDecodeError:
                usage = {}
        rec["tokens"] = int(usage.get("tokens", 0)) if isinstance(usage, dict) else 0
        rec["cost_usd"] = float(usage.get("cost_usd", 0.0)) if isinstance(usage, dict) else 0.0
        st["tokens"] += rec["tokens"]
        st["cost_usd"] = round(st["cost_usd"] + rec["cost_usd"], 6)

        calls = []
        shim_cut = shim_log.exists() and shim_log.stat().st_size < shim_start
        if shim_log.exists():
            with shim_log.open("rb") as f:
                f.seek(shim_start)
                calls = [json.loads(line) for line in f.read().decode().splitlines() if line]
        rec["shim_calls"] = [c["argv"] for c in calls]
        blocked = [c for c in calls if c.get("blocked")]
        rec["changed_files"] = gitops.changed_files(self.work)
        bad_paths = [
            f
            for f in rec["changed_files"]
            if any(fnmatch.fnmatch(f, pat) for pat in pol.forbidden_paths)
        ]
        tampered = self.guard_snapshot() != before or shim_cut

        if res.timed_out:
            rec["outcome"] = "timeout"
            return "worker_timed_out", rec
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

        checks = run_checks(feature["steps"], self.work, pol.check_timeout_seconds)
        rec["checks"] = [{"step": c["step"], "ok": c["ok"]} for c in checks]
        if not all_ok(checks):
            rec["outcome"] = "checks_failed"
            return "checks_failed", rec
        rec["outcome"] = "checks_passed"
        return ("checks_passed" if pol.evaluator else "checks_passed_no_evaluator"), rec

    def evaluate(self, fid: str, rec: dict) -> str:
        cand = gitops.commit_all(self.work, f"candidate {fid} (session {rec['session']})")
        rec["candidate"] = cand
        pol = self.policy
        steps = len(next(f for f in self.features() if f["id"] == fid)["steps"])
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
        listing = self.features()
        for f in listing:
            if f["id"] == fid:
                f["passes"] = True
        (self.work / "feature_list.json").write_text(json.dumps(listing, indent=2) + "\n")
        note = f"Last session: {rec['session']} ({fid} passed)."
        (self.work / "PROGRESS.md").write_text(progress_md(self.state["name"], listing, note))
        sha = gitops.commit_all(self.work, f"{fid}: {self._desc(fid)} (session {rec['session']})")
        self.state["good_commit"] = sha
        self.state["consecutive_failures"] = 0
        rec["commit"], rec["outcome"] = sha, "pass"

    def _desc(self, fid: str) -> str:
        return next(f["description"] for f in self.features() if f["id"] == fid)

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
        if st["sessions"] >= pol.max_sessions:
            return "budget_spent", "budget_sessions"
        if st["tokens"] > pol.max_tokens:
            return "budget_spent", "budget_tokens"
        if st["wall_seconds"] >= pol.max_wall_seconds:
            return "budget_spent", "budget_wall_time"
        if rec and rec.get("outcome") == "rule_broken":
            return "gate_fired", rec["rule"]
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
        (self.work / PENDING_FILE).write_text(text)

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
                self.move(self.evaluate(feature["id"], rec))
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

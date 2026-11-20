"""Checks, and the separate evaluator.

The evaluator is its own command (`gatedcrew evaluate`). It clones the work repo
into a fresh temp folder, checks out the candidate commit and reruns the
feature's checks there. It reads the checks from the last good commit, so a
candidate cannot rewrite its own test. The worker never grades its own work.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from . import gitops
from .proc import run


def check_env() -> dict[str, str]:
    env = {
        k: v
        for k, v in os.environ.items()
        if k in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT")
    }
    env["PATH"] = os.pathsep.join(
        p for p in env.get("PATH", "").split(os.pathsep) if not p.endswith("gatedcrew-shims")
    )
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def run_checks(steps: list[str], cwd: str | Path, timeout: float) -> list[dict]:
    out = []
    for step in steps:
        res = run(["/bin/sh", "-c", step], cwd=cwd, env=check_env(), timeout=timeout)
        out.append(
            {
                "step": step,
                "code": res.code,
                "ok": res.ok,
                "timed_out": res.timed_out,
                "tail": (res.out + res.err)[-300:],
            }
        )
    return out


def all_ok(results: list[dict]) -> bool:
    return bool(results) and all(r["ok"] for r in results)


def evaluate(work: str | Path, commit: str, base: str, feature: str, runs: int, timeout: float):
    listing = json.loads(gitops.git(["show", f"{base}:feature_list.json"], work).out)
    steps = next(f["steps"] for f in listing if f["id"] == feature)
    with tempfile.TemporaryDirectory(prefix="gatedcrew-eval-") as tmp:
        clone = Path(tmp) / "clone"
        gitops.git(["clone", "-q", "--no-hardlinks", str(Path(work).resolve()), str(clone)], tmp)
        gitops.git(["checkout", "-q", "--detach", commit], clone)
        rounds = [run_checks(steps, clone, timeout) for _ in range(max(1, runs))]
    agrees = all(all_ok(r) for r in rounds)
    return {"feature": feature, "commit": commit, "agrees": agrees, "rounds": rounds}


def ground_truth(work: str | Path, commit: str, timeout: float = 60) -> dict[str, bool]:
    """Benchmark only: rerun every feature's checks on `commit` in a clean clone."""
    listing = json.loads(gitops.git(["show", f"{commit}:feature_list.json"], work).out)
    with tempfile.TemporaryDirectory(prefix="gatedcrew-truth-") as tmp:
        clone = Path(tmp) / "clone"
        gitops.git(["clone", "-q", "--no-hardlinks", str(Path(work).resolve()), str(clone)], tmp)
        gitops.git(["checkout", "-q", "--detach", commit], clone)
        return {f["id"]: all_ok(run_checks(f["steps"], clone, timeout)) for f in listing}

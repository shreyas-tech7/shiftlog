"""Command line: gatedcrew init | run | approve | reject | report | verify | evaluate | status
| fake-worker | bench | readme."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="gatedcrew", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="make a work repo from a plain spec")
    s.add_argument("spec")
    s.add_argument("--work", required=True)
    s.add_argument("--policy")

    s = sub.add_parser("run", help="run sessions until done, stopped or a gate fires")
    s.add_argument("--work", required=True)
    s.add_argument("--worker", help="shell command for the worker (overrides policy)")
    s.add_argument("--max-sessions", type=int, help="stop this call after N sessions")

    for name in ("approve", "reject"):
        s = sub.add_parser(name, help=f"{name} a pending gate")
        s.add_argument("--work", required=True)
        s.add_argument("--note", default="")

    s = sub.add_parser("report", help="write the daily report in Markdown")
    s.add_argument("--work", required=True)
    s.add_argument("--date", help="YYYY-MM-DD in UTC; default: every day in the log")
    s.add_argument("--out")

    s = sub.add_parser("verify", help="check the audit log hash chain")
    s.add_argument("--work", required=True)

    s = sub.add_parser("status", help="show the run state")
    s.add_argument("--work", required=True)

    s = sub.add_parser("evaluate", help="separate evaluator: rerun checks in a clean clone")
    s.add_argument("--work", required=True)
    s.add_argument("--commit", required=True)
    s.add_argument("--base", required=True)
    s.add_argument("--feature", required=True)
    s.add_argument("--runs", type=int, default=1)
    s.add_argument("--timeout", type=float, default=60)

    s = sub.add_parser("fake-worker", help="scripted worker for tests and the benchmark")
    s.add_argument("--script", required=True)

    s = sub.add_parser("bench", help="run the fault-injection benchmark")
    s.add_argument("--seed", type=int, default=1)
    s.add_argument("--specs", type=int, default=30)
    s.add_argument("--out", required=True)

    s = sub.add_parser("readme", help="write README tables and docs/index.html from results")
    s.add_argument("--check", action="store_true", help="fail if the files are out of date")

    a = p.parse_args(argv)

    if a.cmd == "init":
        from .spec import init

        work = init(a.spec, a.work, a.policy)
        print(f"initialized {work}")
        return 0
    if a.cmd == "run":
        from .loop import Run

        final = Run(a.work, a.worker).go(a.max_sessions)
        print(f"run state: {final}")
        if final == "PENDING_APPROVAL":
            print((Path(a.work) / "PENDING_APPROVAL.md").read_text())
        return 0 if final in ("DONE", "READY") else 3
    if a.cmd in ("approve", "reject"):
        from . import loop

        try:
            final = getattr(loop, a.cmd)(a.work, a.note)
        except RuntimeError as e:
            print(e, file=sys.stderr)
            return 2
        print(f"run state: {final}")
        return 0
    if a.cmd == "report":
        from .report import daily

        text = daily(a.work, a.date)
        if a.out:
            Path(a.out).write_text(text)
        else:
            print(text)
        return 0
    if a.cmd == "verify":
        from . import audit
        from .spec import state_dir

        sd = state_dir(Path(a.work))
        head = json.loads((sd / "state.json").read_text()).get("audit_head")
        ok, msg = audit.verify(sd / "audit.jsonl", head)
        print(("OK " if ok else "TAMPERED ") + msg)
        return 0 if ok else 1
    if a.cmd == "status":
        from .spec import state_dir

        st = json.loads((state_dir(Path(a.work)) / "state.json").read_text())
        keep = ("machine", "sessions", "tokens", "consecutive_failures", "pending", "good_commit")
        print(json.dumps({k: st[k] for k in keep}, indent=2))
        return 0
    if a.cmd == "evaluate":
        from .evaluate import evaluate

        print(json.dumps(evaluate(a.work, a.commit, a.base, a.feature, a.runs, a.timeout)))
        return 0
    if a.cmd == "fake-worker":
        from .fake_worker import main as fake

        return fake([a.script])
    if a.cmd == "bench":
        from .bench import main as bench

        return bench(a.seed, a.specs, a.out)
    if a.cmd == "readme":
        from .readme import main as readme

        return readme(a.check)
    return 2  # pragma: no cover


if __name__ == "__main__":
    sys.exit(main())

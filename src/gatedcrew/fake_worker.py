"""A scripted stand-in for a coding agent. It drives every test and the benchmark.

It reads the task file that gatedcrew writes, looks up the attempt for this
feature in a JSON script, makes the scripted edits and injects the scripted
fault. Script shape:

    {"F01": [{"edits": {"calc.py": "..."}, "fault": "none", "tokens": 1200}, ...]}

Attempt n of a feature uses entry n, and the last entry repeats after that.
Faults: none, break, claim_done, forbidden_command, network, forbidden_path,
hidden_dependency, timeout, token_burn.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from .proc import run

FAULTS = (
    "none",
    "break",
    "claim_done",
    "forbidden_command",
    "network",
    "forbidden_path",
    "hidden_dependency",
    "timeout",
    "token_burn",
)


def _write(root: Path, rel: str, content: str) -> None:
    target = (root / rel).resolve()
    if root.resolve() not in target.parents:
        raise ValueError(f"fake worker refuses to write outside the work repo: {rel}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def pick(script: dict, feature: str, attempt: int) -> dict:
    plan = script.get(feature) or script.get("*") or [{"fault": "claim_done"}]
    return plan[min(attempt, len(plan)) - 1]


def main(argv: list[str]) -> int:
    script = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    task = json.loads(Path(os.environ["GATEDCREW_TASK"]).read_text(encoding="utf-8"))
    act = pick(script, task["feature"], task["attempt"])
    fault = act.get("fault", "none")
    if fault not in FAULTS:
        raise SystemExit(f"unknown fault {fault!r}")
    root = Path.cwd()
    tokens = int(act.get("tokens", 1000))

    if fault != "claim_done":
        for rel, content in act.get("edits", {}).items():
            _write(root, rel, content)
    if fault == "hidden_dependency":
        for rel, content in act.get("hidden", {}).items():
            _write(root, rel, content)
    if fault == "forbidden_command":
        run(["git", "push", "origin", "main"], timeout=10)
    if fault == "network":
        run(["curl", "-sS", "-m", "2", "http://198.51.100.7/"], timeout=10)
    if fault == "forbidden_path":
        listing = json.loads((root / "feature_list.json").read_text())
        for f in listing:
            if f["id"] == task["feature"]:
                f["passes"] = True
        (root / "feature_list.json").write_text(json.dumps(listing, indent=2) + "\n")
    if fault == "token_burn":
        tokens = 10**9
    usage = {"tokens": tokens, "cost_usd": float(act.get("cost_usd", tokens * 3e-6))}
    Path(os.environ["GATEDCREW_USAGE"]).write_text(json.dumps(usage))
    if fault == "timeout":
        time.sleep(10**6)
    if fault == "claim_done":
        print("All features are complete. Nothing left to do.")
    else:
        print(f"worked on {task['feature']} attempt {task['attempt']} ({fault})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""Build a small work repo plus a fake-worker script for one test."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from gatedcrew.spec import init

SPEC = """# tiny-calc
## add two numbers
check: python3 -c "from calc import add; assert add(2, 3) == 5"
## subtract two numbers
check: python3 -c "from calc import sub; assert sub(5, 3) == 2"
"""

ADD = "def add(a, b):\n    return a + b\n"
SUB = "def sub(a, b):\n    return a - b\n"
GOOD = {"F01": [{"edits": {"calc.py": ADD}}], "F02": [{"edits": {"calc.py": ADD + SUB}}]}

POLICY = """[budget]
max_sessions = {max_sessions}
max_wall_seconds = {max_wall}
session_timeout_seconds = {timeout}
max_tokens = {max_tokens}
backoff_seconds = {backoff}
backoff_max_seconds = 8

[gates]
max_consecutive_failures = {fails}
evaluator = {evaluator}
evaluator_runs = 1
"""


def make(tmp: Path, script: dict, spec: str = SPEC, **pol) -> tuple[Path, str]:
    opts = dict(
        max_sessions=20,
        max_wall=600,
        timeout=20,
        max_tokens=10_000_000,
        backoff=0,
        fails=2,
        evaluator="true",
    )
    opts.update(pol)
    (tmp / "spec.md").write_text(spec)
    (tmp / "policy.toml").write_text(POLICY.format(**opts))
    (tmp / "script.json").write_text(json.dumps(script))
    work = init(tmp / "spec.md", tmp / "work", tmp / "policy.toml")
    worker = f"{sys.executable} -I -m gatedcrew fake-worker --script {tmp / 'script.json'}"
    return work, worker


def events(work: Path) -> list[dict]:
    from gatedcrew import audit
    from gatedcrew.spec import state_dir

    return audit.read(state_dir(work) / "audit.jsonl")


def sessions(work: Path) -> list[dict]:
    return [e for e in events(work) if e["event"] == "session"]

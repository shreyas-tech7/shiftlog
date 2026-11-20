"""Command shims. A folder of tiny scripts goes first on the worker's PATH.

Each script runs `python -I -m gatedcrew.shim <tool> <args>`. The shim logs the call,
blocks it when the policy says so, and otherwise runs the real tool.

This is a tripwire, not a sandbox. A worker that calls `/usr/bin/git` by its full
path, or opens a socket from Python, walks straight past it. See docs/SAFETY.md.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from .policy import load
from .proc import run

SHIM_DIR_NAME = "gatedcrew-shims"
BLOCKED_EXIT = 126


def install(state_dir: Path, tools: list[str]) -> Path:
    shim_dir = state_dir / SHIM_DIR_NAME
    shim_dir.mkdir(parents=True, exist_ok=True)
    for old in shim_dir.iterdir():
        old.unlink()
    for tool in tools:
        if "/" in tool or not tool:
            continue
        path = shim_dir / tool
        path.write_text(
            f'#!/bin/sh\nexec "{sys.executable}" -I -m gatedcrew.shim --state "{state_dir.resolve()}" '
            f'"{tool}" "$@"\n',
            encoding="utf-8",
        )
        path.chmod(0o755)
    return shim_dir


def real_binary(tool: str, path_var: str) -> str | None:
    for folder in path_var.split(os.pathsep):
        if not folder or folder.endswith(SHIM_DIR_NAME):
            continue
        cand = Path(folder) / tool
        if cand.is_file() and os.access(cand, os.X_OK):
            return str(cand)
    return None


def main(argv: list[str]) -> int:
    # The state folder is written into each shim script, so a worker cannot point the
    # shim at a softer policy by changing an environment variable.
    if argv[0] != "--state":
        print("gatedcrew shim: missing --state", file=sys.stderr)
        return 2
    state, tool, args = Path(argv[1]), argv[2], argv[3:]
    policy = load(state / "policy.toml")
    reason = policy.forbidden_reason([tool, *args])
    if (
        tool == "git"
        and not reason
        and any(
            k in ("GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS") or k.startswith("GIT_CONFIG_KEY_")
            for k in os.environ
        )
    ):
        reason = "forbidden_command"  # GIT_CONFIG_COUNT and friends can define aliases
    with (state / "shim.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), "argv": [tool, *args], "blocked": reason}) + "\n")
    if reason:
        print(f"gatedcrew: blocked `{' '.join([tool, *args])}` ({reason})", file=sys.stderr)
        return BLOCKED_EXIT
    real = real_binary(tool, os.environ.get("PATH", ""))
    if real is None:
        print(f"gatedcrew: {tool}: not found", file=sys.stderr)
        return 127
    res = run([real, *args], timeout=policy.session_timeout_seconds, capture=False)
    return res.code if res.code >= 0 else 124


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

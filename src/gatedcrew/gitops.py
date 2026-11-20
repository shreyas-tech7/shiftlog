"""Git calls with a pinned config, so the machine's own git settings cannot change results."""

from __future__ import annotations

import os
from pathlib import Path

from .proc import Result, run

PINNED = [
    "-c",
    "user.name=gatedcrew",
    "-c",
    "user.email=gatedcrew@localhost",
    "-c",
    "commit.gpgsign=false",
    "-c",
    "tag.gpgsign=false",
    "-c",
    "core.hooksPath=/dev/null",
    "-c",
    "init.defaultBranch=main",
    "-c",
    "core.autocrlf=false",
]


def git_env() -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_TERMINAL_PROMPT="0",
        GIT_AUTHOR_DATE=env.get("GATEDCREW_FIXED_DATE", env.get("GIT_AUTHOR_DATE", "")),
        GIT_COMMITTER_DATE=env.get("GATEDCREW_FIXED_DATE", env.get("GIT_COMMITTER_DATE", "")),
    )
    for key in ("GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE"):
        if not env[key]:
            del env[key]
    # gatedcrew's own git must never be a worker shim.
    env["PATH"] = os.pathsep.join(
        p for p in env.get("PATH", "").split(os.pathsep) if not p.endswith("gatedcrew-shims")
    )
    return env


def git(args: list[str], cwd: str | Path, timeout: float = 60, check: bool = True) -> Result:
    res = run(["git", *PINNED, *args], cwd=cwd, env=git_env(), timeout=timeout)
    if check and not res.ok:
        raise RuntimeError(f"git {' '.join(args)} failed: {res.err.strip()}")
    return res


def head(cwd: str | Path) -> str:
    return git(["rev-parse", "HEAD"], cwd).out.strip()


def changed_files(cwd: str | Path) -> list[str]:
    """Tracked changes plus untracked and ignored files, relative to HEAD."""
    out = git(["status", "--porcelain", "--untracked-files=all", "--ignored", "-z"], cwd).out
    files = []
    for entry in out.split("\0"):
        if len(entry) > 3:
            files.append(entry[3:])
    return sorted(set(files))


def commit_all(cwd: str | Path, message: str) -> str:
    git(["add", "-A"], cwd)
    git(["commit", "-q", "--allow-empty", "-m", message], cwd)
    return head(cwd)


def reset_to(cwd: str | Path, sha: str) -> None:
    """Put the working tree back to `sha` and remove every untracked or ignored file
    inside this repo. The `.git` folder (where gatedcrew keeps its state) is untouched."""
    git(["reset", "-q", "--hard", sha], cwd)
    git(["clean", "-q", "-f", "-d", "-x"], cwd)


def tree_matches_head(cwd: str | Path) -> bool:
    return git(["status", "--porcelain", "--untracked-files=all", "--ignored"], cwd).out == ""

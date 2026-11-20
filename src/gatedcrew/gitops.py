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
    "-c",
    "core.fsmonitor=false",
    "-c",
    "core.pager=cat",
]


def git_env() -> dict[str, str]:
    # Drop every inherited GIT_ variable (GIT_DIR, GIT_CONFIG_COUNT, GIT_INDEX_FILE and
    # the rest) and ignore ~/.gitconfig, which a worker can write to.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    for key in ("GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE"):
        if key in os.environ:
            env[key] = os.environ[key]
    env.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
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
    entries = iter(out.split("\0"))
    for entry in entries:
        if len(entry) < 4:
            continue
        files.append(entry[3:])
        if entry[0] in "RC":  # a rename or copy: the next entry is the old path
            files.append(next(entries, ""))
    return sorted({f for f in files if f})


def commit_all(cwd: str | Path, message: str) -> str:
    git(["add", "-A"], cwd)
    git(["commit", "-q", "--allow-empty", "-m", message], cwd)
    return head(cwd)


def reset_to(cwd: str | Path, sha: str) -> None:
    """Put the working tree back to `sha` and remove every untracked or ignored file
    inside this repo. The `.git` folder (where gatedcrew keeps its state) is untouched."""
    # A fresh index drops flags such as assume-unchanged and skip-worktree.
    (Path(cwd) / ".git" / "index").unlink(missing_ok=True)
    git(["reset", "-q", "--hard", sha], cwd)
    clean(cwd)


def clean(cwd: str | Path) -> None:
    """Remove untracked and ignored files. The second -f also removes nested repos."""
    git(["clean", "-q", "-f", "-f", "-d", "-x"], cwd)


def hidden_index_entries(cwd: str | Path) -> list[str]:
    """Paths marked assume-unchanged (lower-case tag) or skip-worktree (S). Both hide
    edits from `git status`, so a worker that sets them is tampering."""
    out = git(["ls-files", "-v", "-z"], cwd).out
    return [
        e[2:] for e in out.split("\0") if len(e) > 2 and (e[0].islower() or e[0] == "S")
    ]  # -f twice: nested repos too


def tree_matches_head(cwd: str | Path) -> bool:
    return git(["status", "--porcelain", "--untracked-files=all", "--ignored"], cwd).out == ""

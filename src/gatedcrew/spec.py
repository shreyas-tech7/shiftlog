"""The initializer: turn a plain spec into a work repo with a feature list and a first commit.

Spec format (Markdown):

    # project-name
    ignore: local/

    ## add two numbers
    check: python3 -c "from calc import add; assert add(2, 3) == 5"

Each `##` heading is one feature. Each `check:` line under it is one shell
command that must exit 0. `ignore:` lines before the first feature go into
the work repo's .gitignore.
"""

from __future__ import annotations

import json
import shlex
import shutil
from pathlib import Path

from . import audit, gitops
from .policy import load as load_policy

STATE = Path(".git") / "gatedcrew"
DEFAULT_IGNORES = ["__pycache__/", "local/", "PENDING_APPROVAL.md"]
DEFAULT_POLICY = Path(__file__).with_name("default_policy.toml")


class SpecError(ValueError):
    pass


def parse(text: str) -> dict:
    name, ignores, features = None, [], []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            features.append({"description": line[3:].strip(), "steps": []})
        elif line.startswith("# ") and name is None:
            name = line[2:].strip()
        elif line.startswith("check:"):
            if not features:
                raise SpecError("a check: line comes before the first ## feature")
            features[-1]["steps"].append(line[len("check:") :].strip())
        elif line.startswith("ignore:") and not features:
            ignores.append(line[len("ignore:") :].strip())
    if not name:
        raise SpecError("the spec needs a '# name' line")
    if not features:
        raise SpecError("the spec needs at least one '## feature'")
    out = []
    for i, f in enumerate(features, 1):
        if not f["steps"]:
            raise SpecError(f"feature {f['description']!r} has no check: line")
        out.append(
            {
                "id": f"F{i:02d}",
                "area": name,
                "description": f["description"],
                "steps": f["steps"],
                "passes": False,
            }
        )
    return {"name": name, "ignores": ignores, "features": out}


INIT_HEAD = """#!/usr/bin/env bash
# Run every check in feature_list.json. Exits non-zero on the first failure.
set -euo pipefail
cd "$(dirname "$0")"
check() { if timeout 120 /bin/sh -c "$2"; then echo "PASS $1"; else echo "FAIL $1"; exit 1; fi; }
"""


def init_sh(features: list[dict]) -> str:
    lines = [INIT_HEAD]
    for f in features:
        lines += [f"check {f['id']} {shlex.quote(step)}" for step in f["steps"]]
    return "\n".join(lines) + "\n"


def progress_md(name: str, features: list[dict], note: str = "") -> str:
    done = [f for f in features if f["passes"]]
    lines = [f"# Progress: {name}", "", f"{len(done)} of {len(features)} features pass.", ""]
    for f in features:
        lines.append(f"- [{'x' if f['passes'] else ' '}] {f['id']} {f['description']}")
    if note:
        lines += ["", note]
    return "\n".join(lines) + "\n"


def state_dir(work: Path) -> Path:
    return Path(work) / STATE


def init(spec_path: str | Path, work: str | Path, policy_path: str | Path | None = None) -> Path:
    spec = parse(Path(spec_path).read_text(encoding="utf-8"))
    policy_src = Path(policy_path) if policy_path else DEFAULT_POLICY
    load_policy(policy_src)  # fail early on a bad policy
    work = Path(work)
    if work.exists() and any(work.iterdir()):
        raise SpecError(f"{work} is not empty")
    work.mkdir(parents=True, exist_ok=True)
    gitops.git(["init", "-q", "-b", "main"], work)
    (work / "feature_list.json").write_text(json.dumps(spec["features"], indent=2) + "\n")
    (work / "PROGRESS.md").write_text(progress_md(spec["name"], spec["features"]))
    (work / "init.sh").write_text(init_sh(spec["features"]))
    (work / "init.sh").chmod(0o755)
    (work / ".gitignore").write_text("\n".join(DEFAULT_IGNORES + spec["ignores"]) + "\n")
    sha = gitops.commit_all(work, f"gatedcrew init: {spec['name']}")
    sd = state_dir(work)
    sd.mkdir(parents=True)
    shutil.copyfile(policy_src, sd / "policy.toml")
    entry = audit.append(
        sd / "audit.jsonl", "init", session=0, commit=sha, features=len(spec["features"])
    )
    state = {
        "name": spec["name"],
        "machine": "READY",
        "good_commit": sha,
        "sessions": 0,
        "tokens": 0,
        "cost_usd": 0.0,
        "wall_seconds": 0.0,
        "consecutive_failures": 0,
        "attempts": {},
        "pending": None,
        "audit_head": entry["hash"],
    }
    (sd / "state.json").write_text(json.dumps(state, indent=2) + "\n")
    return work

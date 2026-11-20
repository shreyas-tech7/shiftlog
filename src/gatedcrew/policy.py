"""Read and check `policy.toml`. Unknown keys and wrong types are errors, never silent defaults."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

NETWORK_TOOLS = ("curl", "wget", "ssh", "scp", "nc", "ftp", "telnet", "rsync")


class PolicyError(ValueError):
    pass


@dataclass
class Policy:
    # [budget]
    max_sessions: int = 20
    max_wall_seconds: float = 3600
    session_timeout_seconds: float = 300
    max_tokens: int = 2_000_000
    backoff_seconds: float = 0
    backoff_max_seconds: float = 60
    # [gates]
    max_consecutive_failures: int = 2
    evaluator: bool = True
    evaluator_runs: int = 1
    # [commands]
    shimmed: list[str] = field(
        default_factory=lambda: ["git", *NETWORK_TOOLS, "pip", "npm", "sudo"]
    )
    forbidden: list[str] = field(
        default_factory=lambda: ["git push", "git remote", "git config", "sudo"]
    )
    allow_network: bool = False
    # [paths]
    forbidden_paths: list[str] = field(
        default_factory=lambda: ["feature_list.json", "init.sh", ".github/**", ".gitignore"]
    )
    # [worker]
    worker_command: str = ""
    check_timeout_seconds: float = 60

    def forbidden_reason(self, argv: list[str]) -> str | None:
        """Return why this command is blocked, or None when it may run."""
        if not argv:
            return None
        tool = Path(argv[0]).name
        if tool in NETWORK_TOOLS and not self.allow_network:
            return "network"
        if tool == "git" and _git_alias_or_env_trick(argv[1:]):
            return "forbidden_command"
        words = [tool, *_subcommand(tool, argv[1:])]
        for rule in self.forbidden:
            parts = rule.split()
            if words[: len(parts)] == parts:
                return "forbidden_command"
        return None


# section -> key -> (attribute, type)
SCHEMA: dict[str, dict[str, tuple[str, type]]] = {
    "budget": {
        "max_sessions": ("max_sessions", int),
        "max_wall_seconds": ("max_wall_seconds", float),
        "session_timeout_seconds": ("session_timeout_seconds", float),
        "max_tokens": ("max_tokens", int),
        "backoff_seconds": ("backoff_seconds", float),
        "backoff_max_seconds": ("backoff_max_seconds", float),
    },
    "gates": {
        "max_consecutive_failures": ("max_consecutive_failures", int),
        "evaluator": ("evaluator", bool),
        "evaluator_runs": ("evaluator_runs", int),
    },
    "commands": {
        "shimmed": ("shimmed", list),
        "forbidden": ("forbidden", list),
        "allow_network": ("allow_network", bool),
    },
    "paths": {"forbidden": ("forbidden_paths", list)},
    "worker": {
        "command": ("worker_command", str),
        "check_timeout_seconds": ("check_timeout_seconds", float),
    },
}


def _git_alias_or_env_trick(args: list[str]) -> bool:
    """`git -c alias.x=push x` or `git -c core.sshCommand=...` hides the real action.
    Block any one-off alias, and any -c that points git at another program or folder."""
    risky = ("alias.", "core.sshcommand", "core.hookspath", "core.fsmonitor", "core.pager")
    for i, a in enumerate(args):
        val = None
        if a == "-c" and i + 1 < len(args):
            val = args[i + 1]
        elif a.startswith("-c") and len(a) > 2:
            val = a[2:]
        elif a.startswith("--config-env"):
            return True
        if val is not None and val.lower().startswith(risky):
            return True
    return False


def _subcommand(tool: str, args: list[str]) -> list[str]:
    """For git, skip global options (`-C dir`, `-c k=v`, `--no-pager`) to find the subcommand."""
    if tool != "git":
        return args[:1]
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"):
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        return [a]
    return []


def _coerce(name: str, value, kind: type):
    if kind is bool:
        if not isinstance(value, bool):
            raise PolicyError(f"{name} must be true or false")
        return value
    if kind is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise PolicyError(f"{name} must be a whole number")
        if value < 0:
            raise PolicyError(f"{name} must not be negative")
        return value
    if kind is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise PolicyError(f"{name} must be a number")
        if value < 0:
            raise PolicyError(f"{name} must not be negative")
        return float(value)
    if kind is str:
        if not isinstance(value, str):
            raise PolicyError(f"{name} must be a string")
        return value
    if kind is list:
        if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
            raise PolicyError(f"{name} must be a list of non-empty strings")
        return list(value)
    raise PolicyError(f"no rule for {name}")  # pragma: no cover


def parse(text: str) -> Policy:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise PolicyError(f"policy.toml is not valid TOML: {e}") from e
    pol = Policy()
    for section, values in data.items():
        if section not in SCHEMA:
            raise PolicyError(f"unknown section [{section}]")
        if not isinstance(values, dict):
            raise PolicyError(f"[{section}] must be a table")
        for key, value in values.items():
            if key not in SCHEMA[section]:
                raise PolicyError(f"unknown key {section}.{key}")
            attr, kind = SCHEMA[section][key]
            setattr(pol, attr, _coerce(f"{section}.{key}", value, kind))
    if pol.max_sessions < 1:
        raise PolicyError("budget.max_sessions must be at least 1")
    if pol.session_timeout_seconds <= 0 or pol.check_timeout_seconds <= 0:
        raise PolicyError("timeouts must be above zero")
    if pol.max_consecutive_failures < 1 or pol.evaluator_runs < 1:
        raise PolicyError("gates.max_consecutive_failures and gates.evaluator_runs must be >= 1")
    # The feature list and gatedcrew's own state can never be opened to the worker.
    for must in ("feature_list.json",):
        if must not in pol.forbidden_paths:
            pol.forbidden_paths.append(must)
    return pol


def load(path: str | Path) -> Policy:
    return parse(Path(path).read_text(encoding="utf-8"))

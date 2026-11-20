"""Test guards.

1. Any socket connection to a host that is not local fails the test.
2. Every test runs inside its own temp directory.
3. git gets a pinned config: GIT_CONFIG_GLOBAL points to a temp file, system config is off.
"""

import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

LOCAL = {"localhost", "127.0.0.1", "::1"}
_real_connect = socket.socket.connect


class NetworkBlocked(RuntimeError):
    pass


def _guarded_connect(self, address):
    host = address[0] if isinstance(address, tuple) else address
    if self.family == socket.AF_UNIX or host in LOCAL:
        return _real_connect(self, address)
    raise NetworkBlocked(f"test tried to reach {host!r}; tests must run offline")


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)
    yield


@pytest.fixture(autouse=True)
def _in_temp_dir_with_pinned_git(tmp_path, monkeypatch):
    cfg = tmp_path / "gitconfig"
    cfg.write_text(
        "[user]\n\tname = test\n\temail = test@localhost\n"
        "[init]\n\tdefaultBranch = main\n[commit]\n\tgpgsign = false\n"
        "[core]\n\thooksPath = /dev/null\n"
    )
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    yield

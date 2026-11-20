"""gatedcrew's own git calls ignore the user's and the worker's git settings."""

import os

from gatedcrew import gitops


def test_own_git_ignores_global_config_and_git_env(tmp_path, monkeypatch):
    """Broken case: a worker wrote core.fsmonitor into ~/.gitconfig, and the script
    then ran inside gatedcrew's own status, commit and reset calls."""
    marker = tmp_path / "ran"
    hook = tmp_path / "fsmon.sh"
    hook.write_text(f"#!/bin/sh\ntouch {marker}\n")
    hook.chmod(0o755)
    cfg = tmp_path / "global.cfg"
    cfg.write_text(f"[core]\n\tfsmonitor = {hook}\n[alias]\n\tst = status\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg))
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "elsewhere"))
    repo = tmp_path / "r"
    repo.mkdir()
    gitops.git(["init", "-q"], repo)
    gitops.git(["status"], repo)
    assert not marker.exists()
    assert "GIT_DIR" not in gitops.git_env()
    assert gitops.git_env()["GIT_CONFIG_GLOBAL"] == os.devnull

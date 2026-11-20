"""The command shims: log every call, block forbidden ones, pass the rest to the real tool."""

import json
import os
import sys

from gatedcrew.policy import parse
from gatedcrew.proc import run
from gatedcrew.shim import BLOCKED_EXIT, install, real_binary


def setup(tmp_path, policy=""):
    sd = tmp_path / "state"
    sd.mkdir()
    (sd / "policy.toml").write_text(policy)
    shims = install(sd, parse(policy).shimmed)
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_CONFIG_")}
    env.update(GATEDCREW_STATE=str(sd), PATH=f"{shims}{os.pathsep}{os.environ['PATH']}")
    return sd, env


def calls(sd):
    return [json.loads(x) for x in (sd / "shim.jsonl").read_text().splitlines()]


def test_blocked_command_never_runs(tmp_path):
    """Broken case: without the shim, `git push` reaches the real git."""
    sd, env = setup(tmp_path)
    res = run(["git", "push", "origin", "main"], env=env, cwd=tmp_path, timeout=20)
    assert res.code == BLOCKED_EXIT and "blocked" in res.err
    assert calls(sd)[0]["blocked"] == "forbidden_command"


def test_allowed_command_runs_the_real_tool(tmp_path):
    sd, env = setup(tmp_path)
    res = run(["git", "--version"], env=env, cwd=tmp_path, timeout=20)
    assert res.ok
    assert calls(sd) == [{"ts": calls(sd)[0]["ts"], "argv": ["git", "--version"], "blocked": None}]


def test_network_tool_blocked_by_default(tmp_path):
    sd, env = setup(tmp_path)
    assert (
        run(["curl", "http://198.51.100.7"], env=env, cwd=tmp_path, timeout=20).code == BLOCKED_EXIT
    )
    assert calls(sd)[0]["blocked"] == "network"


def test_full_path_walks_past_the_shim(tmp_path):
    """The honest limit: shims are a tripwire, not a sandbox (see docs/SAFETY.md)."""
    sd, env = setup(tmp_path)
    real = real_binary("git", os.environ["PATH"])
    res = run([real, "--version"], env=env, cwd=tmp_path, timeout=20)
    assert res.ok and not (sd / "shim.jsonl").exists()


def test_shim_uses_this_python(tmp_path):
    sd, _ = setup(tmp_path)
    assert sys.executable in (sd / "gatedcrew-shims" / "git").read_text()


def test_shim_ignores_a_state_folder_from_the_environment(tmp_path):
    """Broken case: if the shim read GATEDCREW_STATE, a worker could point it at a
    folder with an empty policy and push."""
    sd, env = setup(tmp_path)
    soft = tmp_path / "soft"
    soft.mkdir()
    (soft / "policy.toml").write_text('[commands]\nforbidden = ["sudo"]\n')
    env["GATEDCREW_STATE"] = str(soft)
    res = run(["git", "push", "origin", "main"], env=env, cwd=tmp_path, timeout=20)
    assert res.code == BLOCKED_EXIT
    assert not (soft / "shim.jsonl").exists()


def test_alias_from_git_config_env_vars_is_blocked(tmp_path):
    """Broken case: GIT_CONFIG_COUNT can define `alias.x=push` with no -c at all."""
    sd, env = setup(tmp_path)
    env.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="alias.x", GIT_CONFIG_VALUE_0="status")
    res = run(["git", "status"], env=env, cwd=tmp_path, timeout=20)
    assert res.code == BLOCKED_EXIT

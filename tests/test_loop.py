"""Scripted scenarios for the session loop: each gate fires, pass commits, fail reverts."""

import json

import pytest
from helpers import ADD, GOOD, SUB, events, make, sessions

from gatedcrew import audit, gitops, loop
from gatedcrew.spec import state_dir

BROKEN_ADD = "def add(a, b):\n    return a - b\n"


def state(work):
    return json.loads((state_dir(work) / "state.json").read_text())


def flags(work):
    return {f["id"]: f["passes"] for f in json.loads((work / "feature_list.json").read_text())}


def test_happy_path_commits_each_feature(tmp_path):
    work, worker = make(tmp_path, GOOD)
    assert loop.Run(work, worker).go() == "DONE"
    assert flags(work) == {"F01": True, "F02": True}
    log = gitops.git(["log", "--format=%s"], work).out.splitlines()
    assert log[0].startswith("F02:") and any(m.startswith("F01:") for m in log)
    assert "2 of 2 features pass" in (work / "PROGRESS.md").read_text()
    assert gitops.tree_matches_head(work)


def test_failed_session_reverts_to_last_commit(tmp_path):
    """Broken case: without the revert, the bad calc.py, an untracked file and an
    ignored file stay in the work repo after the failed session."""
    script = {
        "F01": [
            {
                "fault": "hidden_dependency",
                "edits": {"calc.py": BROKEN_ADD, "notes.txt": "scratch\n"},
                "hidden": {"local/cache.txt": "x"},
            }
        ]
    }
    work, worker = make(tmp_path, script, fails=1)
    before = gitops.head(work)
    assert loop.Run(work, worker).go() == "PENDING_APPROVAL"
    s = sessions(work)[0]
    assert s["outcome"] == "checks_failed" and s["tree_clean"] is True
    assert gitops.head(work) == before
    assert not (work / "calc.py").exists()
    assert not (work / "notes.txt").exists()
    assert not (work / "local").exists()
    # Only the gatedcrew note for the human is left, and it is git-ignored.
    leftovers = gitops.changed_files(work)
    assert leftovers == ["PENDING_APPROVAL.md"]
    (work / "PENDING_APPROVAL.md").unlink()
    assert gitops.tree_matches_head(work)


def test_forbidden_command_gate(tmp_path):
    script = {"F01": [{"fault": "forbidden_command", "edits": {"calc.py": ADD}}]}
    work, worker = make(tmp_path, script)
    assert loop.Run(work, worker).go() == "PENDING_APPROVAL"
    s = sessions(work)[0]
    assert s["rule"] == "forbidden_command"
    assert s["blocked"] == [["git", "push", "origin", "main"]]
    assert state(work)["pending"]["reason"] == "forbidden_command"
    assert "git push origin main" in (work / "PENDING_APPROVAL.md").read_text()
    assert flags(work)["F01"] is False


def test_network_gate(tmp_path):
    script = {"F01": [{"fault": "network", "edits": {"calc.py": ADD}}]}
    work, worker = make(tmp_path, script)
    assert loop.Run(work, worker).go() == "PENDING_APPROVAL"
    assert sessions(work)[0]["rule"] == "network"


def test_forbidden_path_gate_stops_self_grading(tmp_path):
    """Broken case: a worker that flips its own passes flag would count as done."""
    script = {"F01": [{"fault": "forbidden_path", "edits": {"calc.py": ADD}}]}
    work, worker = make(tmp_path, script)
    assert loop.Run(work, worker).go() == "PENDING_APPROVAL"
    s = sessions(work)[0]
    assert s["rule"] == "forbidden_path"
    assert s["forbidden_paths_touched"] == ["feature_list.json"]
    assert flags(work)["F01"] is False


def test_evaluator_disagrees_gate(tmp_path):
    """Broken case: the code imports a git-ignored helper, so the checks pass in the
    work repo but fail in a clean clone. Without the evaluator this counts as a pass."""
    hidden = {
        "fault": "hidden_dependency",
        "edits": {"calc.py": "import sys\nsys.path.insert(0, 'local')\nfrom helper import add\n"},
        "hidden": {"local/helper.py": ADD},
    }
    work, worker = make(tmp_path, {"F01": [hidden, {"edits": {"calc.py": ADD}}]})
    assert loop.Run(work, worker).go() == "PENDING_APPROVAL"
    s = sessions(work)[0]
    assert s["checks"][0]["ok"] is True
    assert s["evaluator"] == {"agrees": False}
    assert s["gate"] == "evaluator_disagrees"
    assert flags(work)["F01"] is False
    # The human approves. The next attempt is honest and passes the evaluator.
    loop.approve(work)
    assert loop.Run(work, worker).go(max_sessions=1) == "READY"
    assert flags(work)["F01"] is True


def test_without_evaluator_a_hidden_dependency_slips_through(tmp_path):
    hidden = {
        "fault": "hidden_dependency",
        "edits": {"calc.py": "import sys\nsys.path.insert(0, 'local')\nfrom helper import add\n"},
        "hidden": {"local/helper.py": ADD},
    }
    work, worker = make(tmp_path, {"F01": [hidden]}, evaluator="false")
    loop.Run(work, worker).go(max_sessions=1)
    assert flags(work)["F01"] is True  # claimed
    from gatedcrew.evaluate import ground_truth

    assert ground_truth(work, gitops.head(work))["F01"] is False  # not true


def test_checks_fail_twice_gate(tmp_path):
    script = {"F01": [{"fault": "break", "edits": {"calc.py": BROKEN_ADD}}]}
    work, worker = make(tmp_path, script, fails=2)
    assert loop.Run(work, worker).go() == "PENDING_APPROVAL"
    ss = sessions(work)
    assert [s["outcome"] for s in ss] == ["checks_failed", "checks_failed"]
    assert ss[0]["gate"] is None and ss[1]["gate"] == "failed_twice"


def test_claim_done_without_edits_fails_checks(tmp_path):
    work, worker = make(tmp_path, {"F01": [{"fault": "claim_done"}]}, fails=1)
    assert loop.Run(work, worker).go() == "PENDING_APPROVAL"
    assert sessions(work)[0]["outcome"] == "checks_failed"


def test_session_budget_runs_out(tmp_path):
    work, worker = make(tmp_path, GOOD, max_sessions=1)
    assert loop.Run(work, worker).go() == "STOPPED"
    stops = [e for e in events(work) if e["event"] == "stopped"]
    assert stops[0]["reason"] == "budget_sessions"
    assert flags(work) == {"F01": True, "F02": False}


def test_token_budget_runs_out(tmp_path):
    script = {"F01": [{"fault": "token_burn", "edits": {"calc.py": ADD}}]}
    work, worker = make(tmp_path, script, max_tokens=50_000)
    assert loop.Run(work, worker).go() == "STOPPED"
    assert [e for e in events(work) if e["event"] == "stopped"][0]["reason"] == "budget_tokens"


def test_wall_time_budget_with_fake_clock(tmp_path):
    ticks = iter(range(0, 10_000, 100))
    work, worker = make(tmp_path, GOOD, max_wall=150)
    final = loop.Run(work, worker, clock=lambda: next(ticks)).go()
    assert final == "STOPPED"
    assert [e for e in events(work) if e["event"] == "stopped"][0]["reason"] == "budget_wall_time"


def test_session_timeout_kills_worker_and_reverts(tmp_path):
    script = {"F01": [{"fault": "timeout", "edits": {"calc.py": ADD}}]}
    work, worker = make(tmp_path, script, timeout=1, fails=1)
    assert loop.Run(work, worker).go() == "PENDING_APPROVAL"
    s = sessions(work)[0]
    assert s["outcome"] == "timeout" and s["tree_clean"] is True
    assert not (work / "calc.py").exists()


def test_backoff_doubles_and_caps(tmp_path):
    waits = []
    script = {"F01": [{"fault": "break", "edits": {"calc.py": BROKEN_ADD}}]}
    work, worker = make(tmp_path, script, backoff=3, fails=5, max_sessions=4)
    loop.Run(work, worker, sleep=waits.append).go()
    assert waits == [3, 6, 8, 8]


def test_approve_resumes_and_reject_stops(tmp_path):
    script = {"F01": [{"fault": "forbidden_command", "edits": {"calc.py": ADD}}]}
    work, worker = make(tmp_path, script)
    loop.Run(work, worker).go()
    assert loop.approve(work, "ok once") == "READY"
    assert not (work / "PENDING_APPROVAL.md").exists()
    assert loop.Run(work, worker).go() == "PENDING_APPROVAL"
    assert loop.reject(work, "no") == "STOPPED"
    assert loop.Run(work, worker).go() == "STOPPED"  # nothing runs after a reject
    kinds = [e["event"] for e in events(work)]
    assert "approved" in kinds and kinds[-1] == "rejected"


def test_approve_needs_a_pending_gate(tmp_path):
    work, _ = make(tmp_path, GOOD)
    with pytest.raises(RuntimeError, match="nothing to approve"):
        loop.approve(work)
    with pytest.raises(RuntimeError, match="nothing to reject"):
        loop.reject(work)


def test_pending_run_does_nothing_until_a_human_acts(tmp_path):
    script = {"F01": [{"fault": "network", "edits": {"calc.py": ADD}}]}
    work, worker = make(tmp_path, script)
    loop.Run(work, worker).go()
    n = len(sessions(work))
    assert loop.Run(work, worker).go() == "PENDING_APPROVAL"
    assert len(sessions(work)) == n


TAMPER_WORKER = """import json, os, pathlib
p = pathlib.Path(os.environ["GATEDCREW_STATE"]) / "audit.jsonl"
lines = p.read_text().splitlines()
e = json.loads(lines[0]); e["features"] = 99; lines[0] = json.dumps(e)
p.write_text("\\n".join(lines) + "\\n")
pathlib.Path("calc.py").write_text("def add(a, b):\\n    return a + b\\n")
"""


def test_worker_that_edits_the_audit_log_fires_a_gate(tmp_path):
    work, _ = make(tmp_path, GOOD)
    (tmp_path / "tamper.py").write_text(TAMPER_WORKER)
    import sys

    assert loop.Run(work, f"{sys.executable} {tmp_path / 'tamper.py'}").go() == "PENDING_APPROVAL"
    s = sessions(work)[-1]
    assert s["rule"] == "tamper"
    # The edited log was put back from the copy saved before the session.
    assert ".git/gatedcrew/audit.jsonl" in s["restored"]
    ok, msg = audit.verify(state_dir(work) / "audit.jsonl", state(work)["audit_head"])
    assert ok, msg
    assert audit.read(state_dir(work) / "audit.jsonl")[0].get("features") != 99


def test_crash_mid_session_is_thrown_away(tmp_path):
    work, worker = make(tmp_path, GOOD)
    (work / "calc.py").write_text("half done\n")
    st = state(work)
    st["machine"] = "CHECK"
    (state_dir(work) / "state.json").write_text(json.dumps(st))
    assert loop.Run(work, worker).go() == "DONE"
    assert [e["event"] for e in events(work)][1] == "recovered"


def test_second_feature_keeps_first(tmp_path):
    script = {"F01": [{"edits": {"calc.py": ADD}}], "F02": [{"edits": {"calc.py": ADD + SUB}}]}
    work, worker = make(tmp_path, script)
    loop.Run(work, worker).go()
    assert (work / "calc.py").read_text() == ADD + SUB


def test_revert_restores_a_changed_tracked_file(tmp_path):
    """Broken case: without `git reset --hard`, the worker's edit to the already
    committed calc.py survives the failed session."""
    script = {
        "F01": [{"edits": {"calc.py": ADD}}],
        "F02": [{"fault": "break", "edits": {"calc.py": "def add(a, b):\n    return 0\n"}}],
    }
    work, worker = make(tmp_path, script, fails=1)
    assert loop.Run(work, worker).go() == "PENDING_APPROVAL"
    good = state(work)["good_commit"]
    assert gitops.head(work) == good
    assert (work / "calc.py").read_text() == ADD
    assert gitops.changed_files(work) == ["PENDING_APPROVAL.md"]


FIX_CALC = "printf 'def add(a, b):\\n    return a + b\\n' > calc.py"
RENAME_WORKER = f"git mv feature_list.json moved.json && {FIX_CALC}"


def test_renaming_a_forbidden_path_fires_the_gate(tmp_path):
    """Broken case: `git status -z` lists a rename as two entries, and the old path has
    no status prefix. Parsing both alike drops the first three letters of the old
    path, so moving feature_list.json slipped past the forbidden path check."""
    work, _ = make(tmp_path, GOOD)
    assert loop.Run(work, RENAME_WORKER).go() == "PENDING_APPROVAL"
    s = sessions(work)[0]
    assert s["rule"] == "forbidden_path"
    assert "feature_list.json" in s["forbidden_paths_touched"]
    assert (work / "feature_list.json").exists() and not (work / "moved.json").exists()


NESTED_WORKER = "git init -q vendor && echo x > vendor/x.txt"


def test_revert_removes_a_nested_repo(tmp_path):
    """Broken case: `git clean -fdx` with one -f skips folders that hold their own
    .git, so a nested repo survived the revert."""
    work, _ = make(tmp_path, GOOD, fails=1)
    loop.Run(work, NESTED_WORKER).go()
    assert not (work / "vendor").exists()


INFO_WORKER = f"echo secret_helper.py >> .git/info/exclude && {FIX_CALC}"


def test_editing_git_info_exclude_fires_tamper(tmp_path):
    """Broken case: .git/info/exclude hides files from git just like .gitignore."""
    work, _ = make(tmp_path, GOOD)
    assert loop.Run(work, INFO_WORKER).go() == "PENDING_APPROVAL"
    assert sessions(work)[0]["rule"] == "tamper"


SHIM_CUT_WORKER = f'git push origin main; : > "$GATEDCREW_STATE/shim.jsonl"; {FIX_CALC}'


def test_wiping_the_shim_log_fires_tamper(tmp_path):
    """Broken case: a worker that runs a blocked command and then empties shim.jsonl
    would hide the blocked call."""
    work, _ = make(tmp_path, GOOD)
    (state_dir(work) / "shim.jsonl").write_text('{"argv": ["git", "status"]}\n')
    assert loop.Run(work, SHIM_CUT_WORKER).go() == "PENDING_APPROVAL"
    assert sessions(work)[0]["rule"] == "tamper"


def test_worker_code_run_by_the_checks_cannot_grade_itself(tmp_path):
    """Broken case: the checks import the worker's calc.py. Run in the work repo after
    the gates, that code could flip every passes flag and loosen policy.toml."""
    work, _ = make(tmp_path, GOOD)
    pol = state_dir(work) / "policy.toml"
    original = pol.read_text()
    evil = (
        "import json, pathlib\n"
        "p = pathlib.Path('feature_list.json')\n"
        "if p.exists():\n"
        "    p.write_text(json.dumps([dict(f, passes=True) for f in json.loads(p.read_text())]))\n"
        f"pathlib.Path({str(pol)!r}).write_text('')\n"
        "def add(a, b):\n    return a + b\n"
    )
    (tmp_path / "evil.py").write_text(evil)
    worker = f"cp {tmp_path / 'evil.py'} calc.py"
    assert loop.Run(work, worker).go() == "PENDING_APPROVAL"
    s = sessions(work)[0]
    assert s["rule"] == "tamper"
    assert flags(work) == {"F01": False, "F02": False}
    assert pol.read_text() == original


def test_timeout_does_not_hide_a_policy_edit(tmp_path):
    """Broken case: a session that timed out skipped every rule check, and the edited
    policy stayed on disk for the next session."""
    work, _ = make(tmp_path, GOOD, timeout=1)
    pol = state_dir(work) / "policy.toml"
    original = pol.read_text()
    worker = f"printf '[commands]\\nforbidden = []\\n' >> {pol} && sleep 5"
    assert loop.Run(work, worker).go() == "PENDING_APPROVAL"
    s = sessions(work)[0]
    assert s["rule"] == "tamper"
    assert pol.read_text() == original


def test_a_bad_line_in_the_shim_log_is_tamper_not_a_crash(tmp_path):
    work, _ = make(tmp_path, GOOD)
    worker = f'echo "not json" >> "$GATEDCREW_STATE/shim.jsonl"; {FIX_CALC}'
    assert loop.Run(work, worker).go() == "PENDING_APPROVAL"
    assert sessions(work)[0]["rule"] == "tamper"


@pytest.mark.parametrize("usage", ['{"tokens": -999999999}', '{"tokens": "lots"}', "[1]"])
def test_bad_usage_numbers_fire_tamper(tmp_path, usage):
    """Broken case: a negative token count lowered the running total below the budget."""
    work, _ = make(tmp_path, GOOD)
    worker = f"echo '{usage}' > \"$GATEDCREW_USAGE\"; {FIX_CALC}"
    assert loop.Run(work, worker).go() == "PENDING_APPROVAL"
    assert sessions(work)[0]["rule"] == "tamper"
    assert state(work)["tokens"] == 0


def test_symlinked_progress_file_does_not_redirect_writes(tmp_path):
    """Broken case: with PROGRESS.md pointing at init.sh, gatedcrew wrote progress text
    into init.sh and committed it."""
    work, _ = make(tmp_path, GOOD)
    before = (work / "init.sh").read_text()
    loop.Run(work, f"ln -sf init.sh PROGRESS.md && {FIX_CALC}").go(max_sessions=1)
    assert (work / "init.sh").read_text() == before
    assert not (work / "PROGRESS.md").is_symlink()


def test_rule_break_on_the_last_session_still_asks_a_human(tmp_path):
    """Broken case: the spent session budget was checked first and hid the push."""
    script = {"F01": [{"fault": "forbidden_command", "edits": {"calc.py": ADD}}]}
    work, worker = make(tmp_path, script, max_sessions=1)
    assert loop.Run(work, worker).go() == "PENDING_APPROVAL"
    assert state(work)["pending"]["reason"] == "forbidden_command"


def test_assume_unchanged_flag_fires_tamper(tmp_path):
    """Broken case: `git update-index --assume-unchanged feature_list.json` hid an edit
    to the feature list from `git status`. A worker can call the real git by its full
    path, so the flag itself counts as tamper."""
    import shutil

    real_git = shutil.which("git")
    work, _ = make(tmp_path, GOOD)
    worker = (
        f"{real_git} update-index --assume-unchanged feature_list.json && "
        f"sed -i 's/false/true/g' feature_list.json && {FIX_CALC}"
    )
    assert loop.Run(work, worker).go() == "PENDING_APPROVAL"
    assert sessions(work)[0]["rule"] == "tamper"
    assert flags(work) == {"F01": False, "F02": False}
    assert gitops.hidden_index_entries(work) == []


def test_ignored_leftovers_are_removed_after_a_pass(tmp_path):
    script = {
        "F01": [
            {
                "fault": "hidden_dependency",
                "edits": {"calc.py": ADD},
                "hidden": {"local/scratch.txt": "x"},
            }
        ]
    }
    work, worker = make(tmp_path, script, evaluator="false")
    loop.Run(work, worker).go(max_sessions=1)
    assert flags(work)["F01"] is True
    assert not (work / "local").exists()

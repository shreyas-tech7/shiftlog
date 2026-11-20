from pathlib import Path

import pytest

from gatedcrew.policy import Policy, PolicyError, load, parse

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name", ["policy.toml", "policy-strict.toml", "policy-no-evaluator.toml"])
def test_examples_parse(name):
    pol = load(ROOT / "examples" / name)
    assert "feature_list.json" in pol.forbidden_paths


def test_default_policy_matches_example():
    assert (ROOT / "src/gatedcrew/default_policy.toml").read_text() == (
        ROOT / "examples/policy.toml"
    ).read_text()


def test_values_are_read():
    pol = parse("[budget]\nmax_sessions = 3\n[gates]\nevaluator = false\n")
    assert pol.max_sessions == 3 and pol.evaluator is False


@pytest.mark.parametrize(
    "text, msg",
    [
        ("[budgets]\nmax_sessions = 3\n", "unknown section"),
        ("[budget]\nmax_session = 3\n", "unknown key"),
        ("[budget]\nmax_sessions = '3'\n", "whole number"),
        ("[budget]\nmax_sessions = true\n", "whole number"),
        ("[budget]\nmax_tokens = -1\n", "negative"),
        ("[budget]\nmax_sessions = 0\n", "at least 1"),
        ("[budget]\nsession_timeout_seconds = 0\n", "above zero"),
        ("[gates]\nevaluator = 'yes'\n", "true or false"),
        ("[commands]\nforbidden = 'git push'\n", "list"),
        ("[commands]\nforbidden = ['']\n", "list"),
        ("budget = 3\n", "must be a table"),
        ("[budget\n", "not valid TOML"),
    ],
)
def test_bad_policies_are_errors(text, msg):
    with pytest.raises(PolicyError, match=msg):
        parse(text)


def test_feature_list_is_always_forbidden():
    pol = parse("[paths]\nforbidden = []\n")
    assert pol.forbidden_paths == ["feature_list.json"]


@pytest.mark.parametrize(
    "argv, reason",
    [
        (["git", "push", "origin", "main"], "forbidden_command"),
        (["git", "-C", "x", "push"], "forbidden_command"),
        (["git", "-c", "a=b", "--no-pager", "push"], "forbidden_command"),
        (["/usr/bin/git", "remote", "add", "o", "u"], "forbidden_command"),
        (["git", "status"], None),
        (["git", "pushx"], "forbidden_command"),  # not on the git allow list
        (["git", "send-pack", "../bare.git"], "network"),
        (["git", "fetch"], "network"),
        (["pip", "-q", "install", "x"], "network"),
        (["curl", "http://x"], "network"),
        (["wget", "x"], "network"),
        (["sudo", "ls"], "forbidden_command"),
        (["ls"], None),
        ([], None),
    ],
)
def test_forbidden_reason(argv, reason):
    assert Policy().forbidden_reason(argv) == reason


def test_allow_network_lets_curl_run():
    assert parse("[commands]\nallow_network = true\n").forbidden_reason(["curl", "x"]) is None


@pytest.mark.parametrize(
    "argv",
    [
        ["git", "-c", "alias.ship=push", "ship", "origin", "main"],
        ["git", "-calias.ship=push", "ship"],
        ["git", "-c", "core.sshCommand=sh -c id", "status"],
        ["git", "-c", "include.path=f.cfg", "status"],
        ["git", "update-index", "--assume-unchanged", "feature_list.json"],
        ["git", "-c", "core.hooksPath=/tmp/h", "status"],
        ["git", "--config-env=alias.x=Y", "x"],
    ],
)
def test_git_alias_and_config_tricks_are_blocked(argv):
    """Broken case: a one-off alias hides `git push` behind a harmless name."""
    assert Policy().forbidden_reason(argv) == "forbidden_command"


def test_plain_git_dash_c_still_allowed():
    assert Policy().forbidden_reason(["git", "-c", "color.ui=never", "status"]) is None


def test_rules_longer_than_two_words_match():
    pol = Policy(forbidden=["git remote add", "pip install"], git_allowed=[], allow_network=True)
    assert pol.forbidden_reason(["git", "remote", "add", "o", "u"]) == "forbidden_command"
    assert pol.forbidden_reason(["git", "remote", "-v"]) is None
    assert pol.forbidden_reason(["pip", "-q", "install", "x"]) == "forbidden_command"


def test_empty_git_allow_list_turns_it_off():
    assert Policy(git_allowed=[]).forbidden_reason(["git", "stash"]) is None


def test_builtin_defaults_match_the_shipped_policy():
    """Broken case: a policy file without [commands] used to lose git commit, reset
    and checkout, because the built-in defaults were weaker than the shipped file."""
    shipped = load(ROOT / "src" / "gatedcrew" / "default_policy.toml")
    assert parse("").forbidden == shipped.forbidden
    assert parse("").git_allowed == shipped.git_allowed
    assert parse("").shimmed == shipped.shimmed
    assert parse("").forbidden_paths == shipped.forbidden_paths

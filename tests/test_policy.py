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
        (["git", "pushx"], None),
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

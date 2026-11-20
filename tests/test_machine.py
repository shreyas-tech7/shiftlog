"""Every row of the transition table, plus the moves that must not exist."""

import pytest

from gatedcrew import machine
from gatedcrew.machine import TRANSITIONS, BadTransition, step


@pytest.mark.parametrize("row", sorted(TRANSITIONS.items()), ids=lambda r: f"{r[0][0]}-{r[0][1]}")
def test_each_transition(row):
    (state, event), target = row
    assert step(state, event) == target


def test_every_state_is_reachable_and_named():
    targets = set(TRANSITIONS.values()) | {machine.READY}
    assert targets == set(machine.STATES)


def test_final_states_have_no_way_out():
    for state in machine.FINAL:
        assert not [k for k in TRANSITIONS if k[0] == state]


def test_pending_only_leaves_by_a_human():
    outs = {e for (s, e) in TRANSITIONS if s == machine.PENDING}
    assert outs == {"approved", "rejected"}


@pytest.mark.parametrize(
    "state, event",
    [
        ("READY", "approved"),
        ("WORK", "committed"),
        ("CHECK", "evaluator_agrees"),
        ("PENDING_APPROVAL", "start"),
        ("STOPPED", "start"),
        ("DONE", "start"),
        ("EVALUATE", "checks_passed"),
    ],
)
def test_illegal_moves_raise(state, event):
    with pytest.raises(BadTransition):
        step(state, event)


def test_a_failed_check_can_never_reach_commit():
    """Broken case: a table with (CHECK, checks_failed) -> COMMIT would commit bad work."""
    assert step("CHECK", "checks_failed") == "REVERT"
    assert step("EVALUATE", "evaluator_disagrees") == "REVERT"


def test_table_markdown_lists_every_row():
    assert machine.table_markdown().count("\n") == len(TRANSITIONS) + 1

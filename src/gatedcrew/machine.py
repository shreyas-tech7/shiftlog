"""The session loop as an explicit state machine.

Every legal move is one row in TRANSITIONS. Any other (state, event) pair is a bug
and raises, so the loop can never wander into a state the table does not name.
"""

from __future__ import annotations

READY = "READY"  # waiting to start a session
PICK = "PICK"  # choose the next feature with passes=false
WORK = "WORK"  # the worker runs under the shims
CHECK = "CHECK"  # run the feature's checks in the work repo
EVALUATE = "EVALUATE"  # separate evaluator reruns the checks in a clean clone
COMMIT = "COMMIT"  # record the pass and commit
REVERT = "REVERT"  # reset the work repo to the last good commit
GATE = "GATE"  # check budgets and failure counters
PENDING = "PENDING_APPROVAL"  # stopped until a human approves or rejects
STOPPED = "STOPPED"  # run over: budget gone or rejected
DONE = "DONE"  # every feature passes

STATES = (READY, PICK, WORK, CHECK, EVALUATE, COMMIT, REVERT, GATE, PENDING, STOPPED, DONE)
FINAL = (STOPPED, DONE)

TRANSITIONS: dict[tuple[str, str], str] = {
    (READY, "start"): PICK,
    (PICK, "feature_found"): WORK,
    (PICK, "no_features_left"): DONE,
    (WORK, "worker_finished"): CHECK,
    (WORK, "worker_timed_out"): REVERT,
    (WORK, "rule_broken"): REVERT,
    (CHECK, "checks_passed"): EVALUATE,
    (CHECK, "checks_passed_no_evaluator"): COMMIT,
    (CHECK, "checks_failed"): REVERT,
    (EVALUATE, "evaluator_agrees"): COMMIT,
    (EVALUATE, "evaluator_disagrees"): REVERT,
    (COMMIT, "committed"): GATE,
    (REVERT, "reverted"): GATE,
    (GATE, "within_budget"): READY,
    (GATE, "budget_spent"): STOPPED,
    (GATE, "gate_fired"): PENDING,
    (PENDING, "approved"): READY,
    (PENDING, "rejected"): STOPPED,
}


class BadTransition(RuntimeError):
    pass


def step(state: str, event: str) -> str:
    try:
        return TRANSITIONS[(state, event)]
    except KeyError:
        raise BadTransition(f"no move from {state} on {event}") from None


def table_markdown() -> str:
    rows = ["| From | Event | To |", "| --- | --- | --- |"]
    rows += [f"| {s} | {e} | {t} |" for (s, e), t in TRANSITIONS.items()]
    return "\n".join(rows)

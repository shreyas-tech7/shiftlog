# Plan

The brief in docs/build/BUILD_PROMPT.md (Part 2) is the spec. No question rounds.
Each step is one or two features in feature_list.json, built test first.

## Steps

1. **Initializer, helper, fixture** (F01 to F03). `spec.py` parses a Markdown spec and makes the work repo. `proc.py` is the one subprocess entry point. `tests/conftest.py` pins git config and puts each test in a temp folder.
2. **Policy** (F04). `policy.py` reads TOML strictly. Unknown keys and wrong types are errors. `examples/` holds three policies.
3. **Fake worker** (F05). `fake_worker.py` reads the task file and a JSON script of edits and faults.
4. **State machine and loop** (F06, F07). `machine.py` holds the table. `loop.py` walks it: pick, work, check, evaluate, commit or revert, gate.
5. **Shims** (F08, F09). `shim.py` writes small scripts that go first on the worker's PATH. Changed-file globs give the forbidden-path gate. A hash of state, config, hooks and refs gives the tamper gate.
6. **Evaluator** (F10). `gatedcrew evaluate` clones the candidate commit into a temp folder and reruns the checks from the last good commit.
7. **Budgets and approval** (F11, F12). Sessions, tokens, wall time, backoff, session timeout, fail twice, approve, reject.
8. **Audit log** (F13). `audit.py`, hash chain, head hash in state.json.
9. **Report** (F14). `report.py`.
10. **Benchmark** (F16). `bench.py`: 30 fixed specs, seeded fault plans, paired arms with and without the evaluator, seeds 1 and 2.
11. **Docs and release** (F17 to F21). Generated README, safety page, study-later kit, CI, release check, hand-off.

## Assumptions

- "Plain spec" means a small Markdown file with `##` features and `check:` lines.
- Tokens and cost come from what the worker reports in a usage file. The fake worker reports synthetic numbers.
- A spent budget ends the run. Rule gates ask a human.
- "Approve" means go on with the next session. "Reject" ends the run.
- The benchmark's simulated human approves up to 4 gates per spec, then rejects.
- Fault rates in the benchmark are made up to exercise every gate. They are not measured from any agent.

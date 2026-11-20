# Interview questions and answers

Each answer points at the code (file and function) and the results (file and number).
Numbers come from `results/bench-seed1.json` and `results/bench-seed2.json`, which a
scripted fake worker produced. No model ran.

**1. What does gatedcrew do, in one breath?**
It runs a coding agent one feature at a time in short sessions, checks every result in
a clean clone, reverts every failure, writes a hash-chained log, and stops for a human
when a rule fires. The loop is `Run.go` in `src/gatedcrew/loop.py`.

**2. Why a separate evaluator instead of letting the agent grade itself?**
An agent that grades itself grades what it can see, and it tends to praise its own
work. The evaluator (`evaluate` in `src/gatedcrew/evaluate.py`) runs as its own process,
clones the candidate commit into a temp folder and reads the checks from the last good
commit. In the benchmark the arm without it claimed far more than it delivered: on seed 2,
99.1% of features were flagged passing but only 73.7% passed in a clean rerun (29 false
passes). With the evaluator there were 0 false passes on both seeds.

**3. What kind of bug does the evaluator catch that the worker's own check run misses?**
Anything that only works in the dirty working copy. The benchmark's `hidden_dependency`
fault imports a helper from a git-ignored folder. The checks pass in the work repo and fail
in a clean clone. `tests/test_loop.py::test_evaluator_disagrees_gate` shows it.

**4. What does each gate prevent?**
`forbidden_command` stops pushes, history rewrites and config changes. `network` stops
calls out of the machine. `forbidden_path` stops the worker from editing its own
`passes` flag or hiding files with `.gitignore`. `tamper` stops edits to the log, state,
config, hooks and refs. `evaluator_disagrees` stops self-praise. `failed_twice` stops a
dead end from eating the budget. Budgets stop runaway cost. See `Run.gate` and `Run.session`.

**5. What can gatedcrew not do?**
It cannot contain a hostile worker. A full path like `/usr/bin/git` skips the shim, a
Python socket skips the network rule, and writes outside the work repo go unseen. The
test `test_full_path_walks_past_the_shim` shows the first one on purpose. `docs/SAFETY.md`
lists the rest. It is a tripwire for honest but careless agents, not a sandbox.

**6. Why is the loop a state machine with a table?**
Long runs fail in odd orders: a timeout during checks, a crash between commit and log.
With a table (`TRANSITIONS` in `src/gatedcrew/machine.py`) any move that is not listed
raises. `tests/test_machine.py` tests every row, and a test asserts that a failed check
can never reach COMMIT.

**7. How does the revert work, and how do you know it is complete?**
`gitops.reset_to` runs `git reset --hard <good>` and `git clean -fdx`. The `-x` removes
ignored files too, so a hidden helper cannot survive. `tree_matches_head` then checks
`git status --ignored`. Two tests prove it: one with a changed tracked file and one with
untracked and ignored files. A mutation check (turning off the reset) makes the first fail.

**8. How does the audit log show edits?**
Each line stores `prev`, the hash of the line before, and `hash`, the SHA-256 of its own
canonical JSON (`audit.append`). `audit.verify` walks the chain. The newest hash also lives
in `state.json`, so cutting lines off the end shows up. `tests/test_audit.py` covers an
edit, an edit with a recomputed hash, a deleted line, a cut tail and a garbage line.

**9. Why put the run state in `.git/gatedcrew/`?**
`git clean -x` never touches `.git`, the evaluator's clone never copies it, and `git status`
never shows it. A worker can still reach it, which is why the tamper gate hashes it.

**10. How do you make sure every subprocess has a timeout?**
There is one helper, `proc.run`, and it refuses a missing or zero timeout. A test
(`tests/test_proc.py::test_no_subprocess_outside_the_helper`) scans `src`, `scripts` and
`tests` for any other way to start a process. A second test plants a bad file to show the
scan catches it.

**11. What does the benchmark measure, and what does it not?**
It measures how the harness reacts to scripted faults: completion in a clean rerun, false
passes, wasted sessions and gate triggers, with and without the evaluator. It does not
measure any model. The fault rates in `bench.FIRST` and `bench.LATER` are made up to
exercise every gate.

**12. Where do the 95% intervals come from?**
A bootstrap over specs, 2,000 resamples (`bench.bootstrap`). Features inside a spec share a
run, so resampling single features would make the interval too narrow. Gate counts are fixed
counts per seed and get no interval.

**13. The evaluator wastes more sessions. Is that bad?**
On seed 1 it wasted 73 sessions against 58 without it, and on seed 2 it wasted 102 against 64.
Those extra sessions are the cost of catching false passes. Without it the run looks cheaper
and finishes fewer features for real (87.7% against 97.4% on seed 1).

**14. How would you use this on a real overnight job?**
Write a spec with real checks, pick a policy from `examples/`, and pass your agent's command
line as `--worker`. Run it as a user with no push rights, in a throwaway clone. In the morning
read `gatedcrew report`, run `gatedcrew verify` and read the diff. The real-agent run is a
human step in `docs/HUMAN_STEPS.md`.

**15. What would you build next?**
A signed audit head so a forged chain needs a key, an opt-in real sandbox (`bwrap` or a
container), and per-gate allowances on approve. They are in `docs/PROPOSALS.md`.

**16. How does this relate to Anthropic's harness posts?**
It takes the initializer plus coding sessions pattern and the separate evaluator role from
those posts, and adds written policy, approval gates, a hash-chained log and a fault benchmark.
Their example of a 6 hour, $200 multi-agent run against a 20 minute, $9 solo run is the reason
budgets exist here.

# Walkthrough

A tour of every file. Short sentences, one idea each.

## The big picture

gatedcrew watches a coding agent while it works.
The agent is called the worker.
The worker gets one feature at a time.
Each try is a session.
After each session gatedcrew decides: keep the work, throw it away, or ask a human.

## Source code (`src/gatedcrew/`)

### `proc.py`
This is the only file that starts other programs.
Every call needs a timeout.
On a timeout it kills the program and all of its children.
A test reads every Python file and fails if any other file starts a program.

### `gitops.py`
This file runs git for gatedcrew.
It always passes the same settings: name, email, no signing, no hooks.
So your own git settings cannot change what happens.
`reset_to` throws away a failed session. It runs `git reset --hard` and `git clean -fdx`.
`tree_matches_head` checks that nothing is left over.

### `spec.py`
This is the initializer.
It reads a plain Markdown spec. Each `##` heading is a feature. Each `check:` line is a test command.
It makes the work repo: `feature_list.json`, `PROGRESS.md`, `init.sh` and `.gitignore`.
It makes the first commit.
It creates `.git/gatedcrew/`, where the run state, the policy copy and the audit log live.

### `policy.py`
This file reads `policy.toml`.
It knows four kinds of settings: budgets, gates, commands and paths.
An unknown key or a wrong type is an error. It never guesses.
`forbidden_reason` says if a command is blocked and why.

### `default_policy.toml`
The policy used when you do not pass one. It matches `examples/policy.toml`.

### `machine.py`
The state machine.
`TRANSITIONS` is a table: from this state, on this event, go to that state.
Any move that is not in the table raises an error.
This keeps the loop honest.

### `loop.py`
The heart of gatedcrew.
`Run.go` walks the state machine until the run is done, stopped or waiting for a human.
`session` runs the worker once. Then it looks at what the worker did.
It reads the shim log, lists changed files and compares hashes for tampering.
Then it runs the feature's checks.
`evaluate` makes a candidate commit and asks the separate evaluator.
`commit_pass` sets the `passes` flag and commits.
`revert` resets the work repo and waits a bit (backoff).
`gate` checks the budgets and the failure counters.
`approve` and `reject` are what a human runs when a gate fires.

### `shim.py`
Small scripts named `git`, `curl` and so on.
They sit first on the worker's PATH.
Each call is logged. Forbidden calls are blocked with exit code 126.
Allowed calls run the real tool.
A worker that uses a full path like `/usr/bin/git` gets past them. That is a known limit.

### `evaluate.py`
`run_checks` runs check commands with a clean environment and a timeout.
`evaluate` is the separate evaluator. It clones the repo into a temp folder and reruns the checks there.
It reads the checks from the last good commit, so the worker cannot change its own test.
`ground_truth` is for the benchmark. It reruns every check on the final commit.

### `audit.py`
The audit log. One JSON object per line.
Each line keeps the hash of the line before it.
`verify` walks the chain and finds the first broken line.
The newest hash is also saved in `state.json`, so a cut tail shows too.

### `report.py`
The daily report. One Markdown page.
It shows the status, the numbers, each feature, each failed session, human decisions and the next step.

### `fake_worker.py`
A pretend agent for tests and the benchmark.
It reads a JSON script: which files to write and which fault to inject.
Faults: break, claim done, forbidden command, network, forbidden path, hidden dependency, timeout, token burn.

### `bench.py`
The benchmark. 30 small specs with fixed content.
A seed picks a fault for each attempt.
Each spec runs with the evaluator and without it, on the same faults.
A pretend human approves up to 4 gates per spec.
`summarize` adds it all up, with bootstrap intervals over specs.

### `readme.py`
Writes the result tables into README.md and builds `docs/index.html`.
`--check` fails if the files do not match the result files.

### `cli.py`, `__main__.py` and `__init__.py`
The `gatedcrew` command and its subcommands. `__init__.py` holds the version.

## Tests (`tests/`)

- `conftest.py`: blocks the network, puts every test in a temp folder, pins git settings.
- `helpers.py`: builds a small work repo and a script for one test.
- `test_loop.py`: one scenario per gate, plus commit, revert, timeout, backoff, approve, reject, tamper and crash recovery.
- `test_machine.py`: every row of the state table.
- `test_proc.py`: timeouts, process trees, and the scan for stray process calls.
- `test_policy.py`, `test_init.py`, `test_shim.py`, `test_audit.py`, `test_report.py`, `test_cli.py`.
- `test_bench.py`, `test_readme.py`, `test_repo.py`: benchmark, generated docs, repo files.
- `test_network_guard.py`: proves the network block works.

## Other files

- `init.sh`: one command to install and test everything.
- `examples/`: a spec, its fake-worker script and three policies.
- `bench/specs/`: the 30 benchmark specs as plain files.
- `results/`: benchmark output for seeds 1 and 2.
- `scripts/check_links.py`: checks links in Markdown and HTML.
- `scripts/make_demo.py`: makes `docs/DEMO.md` from a real run.
- `scripts/make_social_preview.py`: draws `docs/social-preview.png`.
- `docs/SAFETY.md`: what gatedcrew catches and what it misses.
- `docs/INTERVIEW_QA.md`: questions and answers.
- `docs/HUMAN_STEPS.md`: what only Shreyas can do.
- `PROGRESS.md`, `BLOCKERS.md`, `DECISIONS.md`, `feature_list.json`: the build's own memory.

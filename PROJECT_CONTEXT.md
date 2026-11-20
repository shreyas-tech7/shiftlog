# Project context: gatedcrew (repo `shiftlog`)

## What it is
gatedcrew runs a coding agent in short, logged sessions under written rules for
budgets and approvals. One session works on one feature. A separate evaluator
reruns the checks in a clean clone. A failed session is always reverted. When a
rule fires, the run stops and waits for `gatedcrew approve` or `gatedcrew reject`.
It logs and gates. It is not a sandbox.

## Status
See PROGRESS.md. Release candidate v0.1.0-rc1 on branch `claude/build-shiftlog`.

## Stack
Python 3.11+, standard library only, git. pytest and ruff for development.
Policy files are TOML (`tomllib`).

## Commands
- `./init.sh`: make `.venv`, install, lint, link check, all tests offline.
- `gatedcrew init SPEC --work DIR [--policy FILE]`
- `gatedcrew run --work DIR --worker "CMD"`
- `gatedcrew approve|reject --work DIR`
- `gatedcrew report --work DIR`, `gatedcrew verify --work DIR`
- `gatedcrew bench --seed 1 --out results/bench-seed1.json`
- `gatedcrew readme` writes README tables and docs/index.html from results.

## Layout
- `src/gatedcrew/proc.py`: the only place that starts a process.
- `gitops.py`: git with a pinned config.
- `spec.py`: the initializer. `policy.py`: the policy parser.
- `machine.py`: the state table. `loop.py`: the session loop, gates, approve, reject.
- `shim.py`: command shims. `evaluate.py`: checks and the separate evaluator.
- `audit.py`: hash-chained JSON Lines log. `report.py`: daily report.
- `fake_worker.py`: scripted worker. `bench.py`: benchmark. `readme.py`: generated docs.
- `examples/`: specs and policies. `bench/specs/`: the 30 benchmark specs.
- `results/`: benchmark result files. `docs/`: safety page, study-later kit, hand-off.

## Rules
- Every subprocess goes through `proc.run` with a timeout. A test enforces it.
- Tests run offline, in temp folders, with pinned git config.
- Never start a real agent as the worker in a build session. Fake worker only.
- Never type numbers into README.md. Run `gatedcrew readme`.
- Only the `passes` flags in feature_list.json may change.

## Skills that fit
superpowers test-driven-development, systematic-debugging,
verification-before-completion, requesting-code-review; security-audit.

## Do not read
`.venv/`, `docs/build/BUILD_PROMPT.md` (unless resuming), `results/*.json` runs arrays.

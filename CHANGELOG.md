# Changelog

## v0.1.0-rc1 (2026-11-20)

First release candidate.

- `gatedcrew init`: plain Markdown spec to a work repo with `feature_list.json`, `PROGRESS.md`, `init.sh` and a first commit.
- `gatedcrew run`: session loop as an explicit state machine. Commit on pass, revert on fail.
- Separate evaluator (`gatedcrew evaluate`) that reruns checks in a clean clone.
- `policy.toml` with budgets (sessions, wall time, tokens, backoff, session timeout) and rules (forbidden commands, network, forbidden paths).
- Gates: forbidden command, network, forbidden path, tamper, evaluator disagrees, failed twice. `gatedcrew approve` and `gatedcrew reject`.
- Hash-chained JSON Lines audit log and `gatedcrew verify`.
- `gatedcrew report`: daily report in Markdown.
- Scripted fake worker and a 30-spec fault-injection benchmark, with and without the evaluator, seeds 1 and 2.
- Hardening from the release check: checks run on a copy of the tree, protected files are written back after every session, rules are checked on every exit, a git allow list, a locked git environment, network subcommands blocked, checks on the shim log, usage numbers and hidden index flags, symlink-safe writes, and a timeout that cannot hang. See docs/RELEASE_CHECK.md.
- `examples/claude-code-worker.sh`: a worker adapter for a real coding agent. Not run in this build.

Release commit: recorded in docs/HUMAN_STEPS.md after the release check.

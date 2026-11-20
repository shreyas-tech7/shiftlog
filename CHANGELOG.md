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

Release commit: recorded in docs/HUMAN_STEPS.md after the release check.

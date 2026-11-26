# Progress

## Done
- Initializer, subprocess helper with scan test, pinned-git temp fixture.
- Policy parser and examples. Fake worker with scripted faults.
- State machine table, session loop, commit on pass, revert on fail.
- Shims, git allow list, forbidden-command and network gates. Forbidden-path and tamper gates.
- Separate evaluator. Budgets, backoff, timeout. Fail-twice gate. Approve and reject.
- Audit log hash chain with tamper tests. Daily report.
- Benchmark on seeds 1 and 2, generated README and results page, demo, docs, CI, social preview.
- Release check: outside check, code and security review, scans, mutation checks. All findings fixed or logged. See docs/RELEASE_CHECK.md.
- Hand-off: CHANGELOG, docs/HUMAN_STEPS.md, real-agent adapter in examples/.

## Next
- Human steps only, in docs/HUMAN_STEPS.md: create `main`, open and merge the pull request, tag v0.1.0-rc1, first run with a real agent.

## Open blockers
See BLOCKERS.md (name taken on npm, skill installs skipped, no gh, accepted risks).

## Last ./init.sh
2026-11-20: ruff clean, format clean, links ok, all tests passed offline.

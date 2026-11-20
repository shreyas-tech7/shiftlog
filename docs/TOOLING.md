# Tooling

| Tool | Source | Version | Why | Check result |
| --- | --- | --- | --- | --- |
| superpowers skills | already in the session (claude.ai account) | as installed | plans, TDD, debugging, verification | applied inline, one feature at a time |
| ponytail, caveman, humanizer | `npx skills add ...` | none | code style, terse progress, doc pass | not installed. Earlier builds in this project had the install denied by the permission system, so it was not retried. Their rules were applied by hand |
| security-audit | `anthropic-skills:security-audit`, in the session's skill list | as installed | release check audit | see docs/RELEASE_CHECK.md |
| gitleaks | `go install github.com/zricethezav/gitleaks/v8@latest` | v8.30.1 tree (go install build) | secret scan before each commit | installed |
| actionlint | `go install github.com/rhysd/actionlint/cmd/actionlint@latest` | v1.7.12 | workflow lint | installed |
| pip-audit | `uv tool install pip-audit` | latest on 2026-11-20 | dependency audit | installed |
| ruff | PyPI (dev extra) | at install time | lint, format, `--select S` | runs in init.sh |
| graphify, cisco-ai-skill-scanner, pre-commit | `uv tool install` | not installed | not needed: under 30 source files, no new skills installed, gitleaks runs directly | skipped |

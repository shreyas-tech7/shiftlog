# Blockers

Each entry: what failed, the exact error, and what was done instead.

1. **Name `shiftlog` is taken on npm** (2026-11-20). `https://registry.npmjs.org/shiftlog` answers 200 (a name reservation for an agent handoff kit, created 2026-08-11). PyPI answers 404. The section 4 rule needs both registries free. Instead: the package and command are named `gatedcrew`, the brief's backup name (PyPI 404, npm 404, no well-known GitHub project in a web search). The repo stays `shiftlog`. Manual step: rename the repo, in docs/HUMAN_STEPS.md.
2. **Skill installs skipped** (ponytail, caveman, humanizer via `npx skills add`). Earlier builds in this project had these installs denied by the permission system, so they were not retried. Instead: their rules were applied by hand (small plain code, terse progress, plain-word docs). Logged in docs/TOOLING.md.
3. **`gh` CLI, pull requests and tag pushes do not work from this machine.** Instead: the release SHA is in CHANGELOG.md and docs/HUMAN_STEPS.md, the About text is in docs/GITHUB_ABOUT.md and the topics are in docs/topics.txt. The coordinator or Shreyas sets them.
4. **Accepted risks from the release check** (2026-11-20). The code review and the outside check found more than this build could close. The ones left open:
   - The shims match words, not intent. A worker can run any program, and that program can call the real git by its full path or open a socket. The tamper hash, the restore and the fresh index catch the common results. Running the worker as a user with no keys stays the real fix, as docs/SAFETY.md says.
   - A crash of gatedcrew itself mid session is thrown away on the next run with a `recovered` log line and no gate.
   - `fnmatch` patterns in `[paths] forbidden` let `*` match across `/`. They are not gitignore patterns.
   - The process scan in tests/test_proc.py does not look for `multiprocessing` or dynamic imports.
   - `audit.last_hash` reads the whole log on every append. Fine at overnight scale, slow at a million lines.

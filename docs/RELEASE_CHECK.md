# Release check

Run on 2026-11-20 on branch `claude/build-shiftlog`, before the v0.1.0-rc1 release commit. Each step follows section 11 of the build brief.

| Step | How it ran | Result |
| --- | --- | --- |
| 1. Review of the branch diff | A subagent that did not write the code read the whole diff, in the ponytail style, because the review skill could not be installed here | Six must-fix items and five nice-to-haves. All must-fix items are fixed. Three nice-to-haves are fixed (recursive hook hashing, defaults that match the shipped policy, the comment in `parse`). The rest are in `BLOCKERS.md`. |
| 2. Security audit | The same subagent audited the gates, the policy parser, the revert step and the hash chain with working repros, and read every NEEDS VALIDATION item. I also patched five gaps I found myself before it reported | Nine confirmed findings. All nine are fixed, each with a test that fails when the fix is removed. Details below. |
| 3. Scans | `gitleaks git -v .`, `pip-audit` on the venv, `ruff check --select S`, `actionlint`, `scripts/check_links.py` | gitleaks: no leaks. pip-audit: no known vulnerabilities. ruff S: three S311 notes on `random.Random(seed)` in the benchmark, which is seeded on purpose and not used for security. actionlint: clean. Links: ok. |
| 4. Humanizer | By hand on `README.md` and `docs/*.md`, because the humanizer skill could not be installed here | Plain words kept. The writing-rules test passes on every doc. |
| 5. Outside check | One subagent that did not write the code cloned the repo into a temp folder, ran `./init.sh` and checked each Done-means item with its own commands | Seven items passed and one was partial (a grandchild in its own session could hang the timeout). It also found seven bugs. All are fixed, and the stale cost table was fixed by rerunning both seeds. |
| 6. Clean state | `git status` and the `passes` flags in `feature_list.json` | Clean after the release commit. Every flag was set only after its own steps passed. |

## What the audit and the outside check found, and the fix

| Finding | Fix | Test |
| --- | --- | --- |
| The checks ran the worker's code in the work repo after the gates, so that code could flip every `passes` flag and empty the policy | Checks run on a copy of the tree. gatedcrew hashes again after them. The new feature list comes from the last good commit | `test_worker_code_run_by_the_checks_cannot_grade_itself` |
| A timed out session skipped the rule checks, and the edited policy stayed on disk | Rules are checked on every exit. Policy, log, git config, hooks and shim scripts are written back after every session | `test_timeout_does_not_hide_a_policy_edit` |
| gatedcrew's own git read `~/.gitconfig` and inherited `GIT_` variables, so a worker could run code inside it | Every `GIT_` variable is dropped, global config is `/dev/null`, `core.fsmonitor` and `core.pager` are pinned | `test_own_git_ignores_global_config_and_git_env` |
| Pushes got past the forbidden list with `-c alias`, `include.path`, `GIT_CONFIG_COUNT` and `git send-pack` | A git allow list, a longer list of blocked `-c` keys, and a block on git calls made with `GIT_CONFIG_COUNT` set | `test_git_alias_and_config_tricks_are_blocked`, `test_alias_from_git_config_env_vars_is_blocked` |
| `git fetch`, `git clone` and `pip install` reached the network with `allow_network = false` | Network subcommands are blocked with the network tools | `test_forbidden_reason` |
| `git update-index --assume-unchanged` hid an edit to the feature list | Off the allow list. Any hidden index flag is tamper, and the revert rebuilds the index | `test_assume_unchanged_flag_fires_tamper` |
| A renamed forbidden file went unflagged | Rename entries count both paths | `test_renaming_a_forbidden_path_fires_the_gate` |
| A worker could empty `shim.jsonl` to hide a blocked call, or crash the loop with a bad line | A shorter log or a bad line is tamper | `test_wiping_the_shim_log_fires_tamper`, `test_a_bad_line_in_the_shim_log_is_tamper_not_a_crash` |
| A negative token count reset the token budget | Only non-negative numbers count. Anything else is tamper | `test_bad_usage_numbers_fire_tamper` |
| A symlink in place of `PROGRESS.md` made gatedcrew write into `init.sh` | gatedcrew removes a symlink before it writes its own files | `test_symlinked_progress_file_does_not_redirect_writes` |
| A rule break on the last session of the budget was hidden by the budget stop | Rule gates come before budgets | `test_rule_break_on_the_last_session_still_asks_a_human` |
| A grandchild in its own session made the timeout wait for it | The read after the kill has its own short timeout | `test_timeout_returns_even_if_a_grandchild_keeps_the_pipe_open` |
| Nested repos and ignored leftovers survived | `git clean -ffdx` on revert, and a clean after each pass | `test_revert_removes_a_nested_repo`, `test_ignored_leftovers_are_removed_after_a_pass` |
| `.git/info/exclude` could hide files | `.git/info` and the object alternates file are in the tamper hash and the restore | `test_editing_git_info_exclude_fires_tamper` |
| The README cost table counted the token burn sessions | Both seeds rerun with the current code | `gatedcrew readme --check` |

For each fix I removed it, ran the tests, and saw at least one test fail. Then I put it back.

GitHub Actions ran the CI workflow on each push to the branch. The runs on the first three pushes passed.

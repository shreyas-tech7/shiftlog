# Demo: a real terminal transcript

Made by `python scripts/make_demo.py`. The worker is the scripted fake worker,
so no model and no network take part. The script `examples/tiny-calc-script.json`
injects a forbidden `git push`, a hidden dependency that only works in the work
repo, and a broken edit. The temp folder path is shortened to `$TMP`.

```console
$ gatedcrew init tiny-calc.md --work work
initialized work
$ gatedcrew run --work work --worker "gatedcrew fake-worker --script ../script.json"
run state: PENDING_APPROVAL
# Pending approval

gatedcrew stopped the run and is waiting for a human.

- Gate: `forbidden_command`
- Why: The worker tried a command that the policy forbids.
- Feature: F01, session 1
- Files the worker changed: calc.py
- Blocked commands: git push origin main

The session was reverted. The work repo matches the last good commit.

To go on: `gatedcrew approve --work $TMP/work`
To end the run: `gatedcrew reject --work $TMP/work`
$ gatedcrew approve --work work --note 'push was blocked, go on'
run state: READY
$ gatedcrew run --work work --worker "gatedcrew fake-worker --script ../script.json"
run state: PENDING_APPROVAL
# Pending approval

gatedcrew stopped the run and is waiting for a human.

- Gate: `evaluator_disagrees`
- Why: The checks passed in the work repo but failed in a clean clone.
- Feature: F02, session 3
- Files the worker changed: calc.py, local/helper.py
- Blocked commands: none

The session was reverted. The work repo matches the last good commit.

To go on: `gatedcrew approve --work $TMP/work`
To end the run: `gatedcrew reject --work $TMP/work`
$ gatedcrew approve --work work --note 'the next try will be honest'
run state: READY
$ gatedcrew run --work work --worker "gatedcrew fake-worker --script ../script.json"
run state: DONE
$ gatedcrew verify --work work
OK 12 lines, chain intact
$ git -C work log --format='%h %s'
c67de6c F03: multiply two numbers (session 6)
efb1f4d candidate F03 (session 6)
c8bb37a F02: subtract two numbers (session 4)
b8f4336 candidate F02 (session 4)
3135bc0 F01: add two numbers (session 2)
c0db33e candidate F01 (session 2)
c96556f gatedcrew init: tiny-calc
$ gatedcrew report --work work
# gatedcrew daily report: tiny-calc

- Period: 2026-11-20 to 2026-11-20 (UTC)
- Status: **DONE**
- Audit log: OK, 12 lines, chain intact
- Features passing: 3 of 3

| Sessions | Passed | Wasted | Gates fired | Tokens | Cost (reported) |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 6 | 3 | 3 | 2 | 9,700 | $0.0291 |

## Features

- F01 add two numbers: passes, 2 session(s) in period
- F02 subtract two numbers: passes, 2 session(s) in period
- F03 multiply two numbers: passes, 2 session(s) in period

## Sessions that did not pass

- session 1 F01: rule_broken, gate forbidden_command blocked: `git push origin main`
- session 3 F02: evaluator_disagrees, gate evaluator_disagrees
- session 5 F03: checks_failed

## Human decisions and stops

- approved: forbidden_command push was blocked, go on
- approved: evaluator_disagrees the next try will be honest

## Next step

Nothing. Every feature passes. Read the diff and merge it.
$ sed -i 's/"features": 3/"features": 4/' work/.git/gatedcrew/audit.jsonl
$ gatedcrew verify --work work
TAMPERED line 1 was edited (hash mismatch)
```

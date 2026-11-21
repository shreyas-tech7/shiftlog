# Decisions

One line per choice: the options weighed and the reason.

- Name: `shiftlog` (npm taken) vs `gatedcrew` (PyPI and npm free). Picked `gatedcrew` for the package and command because section 4 says to pick the first free name. The repo keeps the name `shiftlog`.
- Run state lives in `<work>/.git/gatedcrew/` vs a folder in the working tree vs a sibling folder. Picked `.git/gatedcrew/`: `git clean -x` never touches it, the evaluator's clone never copies it, and `git status` never shows it.
- Spec format: Markdown (`# name`, `## feature`, `check:` lines) vs TOML vs YAML. Picked Markdown because the brief says "a plain spec" and it needs no parser library.
- Evaluator runs as a separate process (`python -I -m gatedcrew evaluate`) vs a function call. Picked the process: the brief says it is a separate command, and it reads the checks from the last good commit, not from the candidate.
- Candidate commit then evaluate vs evaluate the dirty tree. Picked a candidate commit: the evaluator clones exactly what would be kept. On disagreement the work repo is reset to the last good commit, so the candidate never stays in the branch history.
- Revert = `git reset --hard <good>` plus `git clean -fdx`. `-x` also removes ignored files, so a hidden helper in an ignored folder cannot survive a failed session.
- Approve means "go on": the failure counter resets and the run continues from READY. Reject ends the run (STOPPED). Simpler than per-gate allowances, and a human can still edit the policy in `.git/gatedcrew/policy.toml`.
- Budget exhaustion stops the run (STOPPED) instead of asking for approval. A spent budget is the human's decision to raise, so it ends cleanly and the report says why.
- Budget checks come before rule gates in the GATE step. A run that is out of budget stops even if the last session also broke a rule. Both are logged.
- Tamper gate: hash gatedcrew's state files, `.git/config`, hooks and refs before and after the worker. Cheap, and it catches a worker that edits the audit log or commits on its own.
- `git commit`, `git reset` and `git checkout` are forbidden for the worker by default, because the loop owns history. `git push`, `git remote` and `git config` are forbidden too.
- The generated work-repo `init.sh` is plain shell with the checks inlined, so no Python subprocess call hides in a string.
- Benchmark: fixed spec content, seeded fault plan, paired arms (same plan with and without evaluator), a simulated human that approves up to 4 gates per spec then rejects.
- Intervals: cluster bootstrap over specs (2,000 resamples, seeded). Features inside one spec share a run, so resampling features alone would be too narrow. The interval covers variation over which scripted faults a seed draws. It says nothing about any model.
- Fault weights for the first attempt: none 40%, break 15%, hidden dependency 12%, claim done 8%, forbidden command 8%, forbidden path 7%, network 5%, timeout 3%, token burn 2%. Later attempts are cleaner (none 70%). These are made-up rates to exercise every gate. They are not measured from any real agent.
- No dependencies beyond the standard library. pytest and ruff are dev only.
- Git allow list vs a longer deny list (release check). Picked an allow list (`[commands] git_allowed`). A deny list lost to one-off aliases, `include.path`, `GIT_CONFIG_COUNT` and `send-pack`. An allow list closes the whole class. An empty list turns it off.
- Where the work-repo checks run (release check). Picked a copy of the work tree with ignored files and no `.git`. The checks run the worker's code, so running them in the work repo after the gates let that code grade itself. The copy keeps ignored files, so a hidden dependency still passes there and the evaluator still catches it.
- Restore vs only detect (release check). gatedcrew now writes its policy, log, git config, hooks and shim scripts back after every session. Detecting alone left a loosened policy in place for the next session.

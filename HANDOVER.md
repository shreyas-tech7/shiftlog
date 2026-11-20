# Handover

Branch: `claude/build-shiftlog`. Resume with the launcher in docs/build/BUILD_PROMPT.md section 13.

State: every feature in feature_list.json passes. The build is complete. What is left is in
docs/HUMAN_STEPS.md: create `main`, open and merge the pull request, tag v0.1.0-rc1, rename the
repo to `gatedcrew` if wanted, make it public when ready, and start the first real-agent run.

Commands:

```bash
./init.sh
.venv/bin/gatedcrew bench --seed 1 --out results/bench-seed1.json
.venv/bin/gatedcrew readme          # after any benchmark rerun
.venv/bin/python scripts/make_demo.py
```

If a change touches the loop, the policy or the shims, rerun both seeds and `gatedcrew readme`,
then check that docs/INTERVIEW_QA.md still cites the same numbers.

Open decisions: none.

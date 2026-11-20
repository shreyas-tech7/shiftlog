#!/bin/sh
# Worker adapter for a real coding agent: Claude Code in print mode.
#
# gatedcrew runs this once per session, inside the work repo, with the task in the
# JSON file named by $GATEDCREW_TASK. Nothing in this build ever ran it. Shreyas
# starts the first run himself (see docs/HUMAN_STEPS.md).
#
#   gatedcrew run --work /tmp/calc --worker "sh $PWD/examples/claude-code-worker.sh"
#
# The agent edits files only. gatedcrew commits, reverts and grades. The agent
# needs network access to its own API, which the shims do not see, so run it under
# a user that cannot read your keys or push to your remotes.
set -eu

: "${GATEDCREW_TASK:?gatedcrew sets GATEDCREW_TASK}"
TASK=$(cat "$GATEDCREW_TASK")

PROMPT="You are one short session inside the gatedcrew harness.
Work only on the feature in this task (JSON):

$TASK

Rules:
- Edit files in the current folder so that every command in \"steps\" passes.
- Do not run git commit, git push, git reset, git checkout or git config.
- Do not edit feature_list.json, init.sh, .gitignore or anything under .git.
- Do not use the network except for your own model calls.
- Stop when the steps pass. gatedcrew checks and commits your work."

# --max-turns keeps one session short. gatedcrew's own session timeout still applies.
exec claude -p "$PROMPT" \
  --max-turns 30 \
  --allowedTools "Read,Edit,Write,Bash(python*),Bash(pytest*),Bash(ls*),Bash(cat*)"

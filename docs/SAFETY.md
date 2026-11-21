# Safety limits

gatedcrew logs and gates. It is not a security sandbox. This page says what it
catches, what it misses, and how to run it with that in mind.

## What it catches

- **Commands on the shim list.** The worker's PATH starts with a folder of small
  scripts named `git`, `curl`, `wget`, `ssh`, `scp`, `nc`, `pip`, `npm`, `sudo` and a few
  more. Each call is logged in `.git/gatedcrew/shim.jsonl`. Calls that the policy
  forbids exit with code 126 and fire a gate. Each shim script has the state
  folder written into it, so changing an environment variable cannot point it at a
  softer policy.
- **Git subcommands off the allow list.** The worker may run only the git
  subcommands in `[commands] git_allowed` (status, diff, log, add, mv and a few more).
  Anything else is blocked, so a one-off alias, `git update-index` or `git send-pack`
  cannot sneak a push or a hidden edit past the forbidden list. A git call made while
  `GIT_CONFIG_COUNT` or `GIT_CONFIG_PARAMETERS` is set is blocked too, because those
  can define an alias with no `-c`.
- **Network subcommands.** With `allow_network = false`, `git fetch`, `git clone`,
  `git pull`, `git ls-remote`, `pip install`, `npm install` and the like are blocked,
  along with `curl`, `wget`, `ssh` and the other network tools.
- **Git tricks that hide a command.** A one-off alias (`git -c alias.ship=push ship`)
  and a `-c` that swaps in another program or folder (`core.sshCommand`,
  `core.hooksPath`, `core.fsmonitor`, `core.pager`, or any `--config-env`) are
  blocked like a forbidden command.
- **Changes to forbidden paths.** After each session gatedcrew lists every changed,
  untracked and ignored file and matches it against `[paths] forbidden`. A rename
  counts both the old and the new path. The feature list is always forbidden.
- **Tampering during a session.** gatedcrew hashes its own state files, the audit
  log, the shim scripts, `.git/config`, the hooks folder, `.git/info`, the object
  alternates file and every ref before and after the worker, and again after the
  checks. A shim log that got shorter or holds a line that is not a call record also
  counts as tampering. So does a usage file with negative or non-number values, and
  an index entry marked assume-unchanged or skip-worktree.
- **Restore after every session.** gatedcrew saves its policy, its audit log, git
  config, hooks, `.git/info` and the shim scripts before the worker starts and writes
  them back after the session, however it ended. A loosened policy never reaches the
  next session.
- **Rules first.** The rule checks run on every session, a timed out one included,
  and a broken rule asks a human even when the same session spent the last of the
  budget.
- **Self-grading.** The checks come from the last good commit. They run on a copy
  of the work tree, not in the work repo, because they run the worker's code. The
  evaluator reruns them in a fresh clone in a separate process. When a feature
  passes, gatedcrew builds the new feature list from the last good commit, never from
  the work tree.
- **Symlinks in place of gatedcrew's files.** Before gatedcrew writes
  `feature_list.json`, `PROGRESS.md`, `PENDING_APPROVAL.md` or the task file, it
  removes a symlink in its place, so the write cannot land in `init.sh` or outside the
  repo.
- **Settings from outside.** gatedcrew's own git calls drop every inherited `GIT_`
  variable, ignore `~/.gitconfig` and the system config, and pin `core.fsmonitor`,
  `core.hooksPath` and `core.pager`. A worker that writes to `~/.gitconfig` cannot run
  code inside gatedcrew's own git.
- **Runaway sessions.** Every subprocess has a timeout. A timeout kills the whole
  process group. If a grandchild in its own session still holds the output pipe,
  gatedcrew stops reading after a few seconds instead of waiting for it.
- **Leftovers.** A failed session ends with `git reset --hard` and `git clean -ffdx`
  inside the work repo, so the tree matches the last good commit. The second `-f`
  also removes nested git repos. The index is rebuilt from scratch, which drops any
  hidden flags. A passing session also ends with `git clean -ffdx`, so ignored
  leftovers do not carry into the next session.

## What it misses

- A worker that calls a tool by its full path (`/usr/bin/git push`) skips the shim.
  The test `tests/test_shim.py::test_full_path_walks_past_the_shim` shows this on purpose.
- A worker that opens a socket from Python, Node or any other language skips the
  network shim.
- A worker that writes outside the work repo, for example into your home folder,
  is not seen. gatedcrew only looks inside the work repo.
- A worker started in its own new session (`setsid`) can outlive the timeout. The
  harness no longer hangs on it, but the process keeps running until it ends.
- The git allow list and the forbidden list match words, not intent. A worker can
  still run any program it likes, and that program can run the real git by its full
  path. The tamper hash and the restore catch the common results (new commits,
  changed config, hidden index flags), not every one.
- The tamper hash does not cover the object store. A worker can add loose objects.
  They do no harm, because refs and HEAD are hashed.
- A worker that edits the state and puts it back inside one session leaves the
  before and after hashes equal. The restore still writes the saved copy back, but a
  blocked command that already ran in that window is not undone.
- A crash of gatedcrew itself mid session is thrown away on the next run with a
  `recovered` line in the log. It does not ask a human first.
- Someone who can rewrite both `audit.jsonl` and `state.json` can build a new
  chain that verifies. The chain shows edits by a worker that does not know to fix
  every later hash and the saved head. It is not a signature.
- Checks are shell commands from the spec. A spec you did not write can run
  anything when gatedcrew runs its checks.

## How to run it

1. Run the worker as a user that cannot read your keys or push to your remotes.
2. Use a throwaway clone or a container for the work repo when the worker is a real agent.
3. Keep `allow_network = false` unless the task needs it.
4. Read `gatedcrew report` and `gatedcrew verify` every morning. Read the diff before you merge.
5. Raise budgets in small steps. A spent budget is a signal, not an error.

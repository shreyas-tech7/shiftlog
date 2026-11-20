# Safety limits

gatedcrew logs and gates. It is not a security sandbox. This page says what it
catches, what it misses, and how to run it with that in mind.

## What it catches

- **Commands on the shim list.** The worker's PATH starts with a folder of small
  scripts named `git`, `curl`, `wget`, `ssh`, `scp`, `nc`, `pip`, `npm`, `sudo` and a few
  more. Each call is logged in `.git/gatedcrew/shim.jsonl`. Calls that the policy
  forbids exit with code 126 and fire a gate.
- **Changes to forbidden paths.** After each session gatedcrew lists every changed,
  untracked and ignored file and matches it against `[paths] forbidden`. The
  feature list is always forbidden.
- **Tampering during a session.** gatedcrew hashes its own state files, the audit
  log, `.git/config`, the hooks folder and every ref before and after the worker.
- **Self-grading.** The checks come from the last good commit. The evaluator
  reruns them in a fresh clone in a separate process.
- **Runaway sessions.** Every subprocess has a timeout. A timeout kills the whole
  process group.
- **Leftovers.** A failed session ends with `git reset --hard` and `git clean -fdx`
  inside the work repo, so the tree matches the last good commit.

## What it misses

- A worker that calls a tool by its full path (`/usr/bin/git push`) skips the shim.
  The test `tests/test_shim.py::test_full_path_walks_past_the_shim` shows this on purpose.
- A worker that opens a socket from Python, Node or any other language skips the
  network shim.
- A worker that writes outside the work repo, for example into your home folder,
  is not seen. gatedcrew only looks inside the work repo.
- A worker started in its own new session (`setsid`) can outlive the timeout.
- A worker that edits the state and puts it back inside one session leaves the
  before and after hashes equal.
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

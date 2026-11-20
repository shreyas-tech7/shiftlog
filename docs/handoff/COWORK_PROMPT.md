# Prompt for Claude Cowork

Paste the text below into Claude Cowork.

```
You are helping me finish the GitHub setup for my private repo shreyas-tech7/shiftlog.
The package inside it is called gatedcrew. Use my browser. I am already signed in to
GitHub.

Do only these steps. Each one is free and can be undone.

1. Open https://github.com/shreyas-tech7/shiftlog/actions and tell me whether the
   latest CI run on the branch claude/build-shiftlog passed. If it failed, copy the
   name of the failing step.
2. Open the repo's main page. If the About box is empty, set the description to the
   text in docs/GITHUB_ABOUT.md and add the topics in docs/topics.txt.
3. Open Settings, General, Social preview, and upload docs/social-preview.png from the
   repo (download it from the branch first).
4. Check that the repo is still private.

Do not make the repo public. Do not rename the repo. Do not publish a package. Do not
enter any key, token or password. Do not sign in to anything for me. Do not pay for
anything. Do not merge pull requests, create tags, create branches or delete branches.

When you finish, write me the next prompt for Claude Code. It must hold:
- Context: gatedcrew is a guardrail harness for long-running coding agents, built on
  branch claude/build-shiftlog of shreyas-tech7/shiftlog.
- What is complete: the list of steps above that you finished.
- What is open: the steps from docs/HUMAN_STEPS.md that are still open.
- This resume launcher, word for word: "Read docs/build/BUILD_PROMPT.md and follow it.
  Resume from PROGRESS.md on branch claude/build-shiftlog. Do not ask questions. Do
  not stop until every Done-means item is true or blocked with a fallback."
```

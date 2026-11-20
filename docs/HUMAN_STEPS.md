# Human steps

These are the steps only Shreyas can do, in order. The build ran with no GitHub CLI, no tag pushes and no way to create `main`.

Release commit: `RELEASE_SHA`

Branch: `claude/build-shiftlog`

1. Create `main` on GitHub from the branch's first commit, `f5f12ee93e8e6119c4f1460390bb85b1a893a972`. On the repo page, open the branch menu, type `main` and pick "Create branch from claude/build-shiftlog", or run `git push origin f5f12ee93e8e6119c4f1460390bb85b1a893a972:refs/heads/main`. Then set `main` as the default branch in Settings, General.
2. Open a pull request from `claude/build-shiftlog` into `main`. Read the diff. Wait for the CI check to pass. Merge with a merge commit, so the release commit stays in the history of `main`.
3. Create the tag on the release commit:

   ```
   git fetch origin
   git tag -a v0.1.0-rc1 RELEASE_SHA -m "Release candidate 1"
   git push origin v0.1.0-rc1
   ```

   Or create a pre-release named `v0.1.0-rc1` on that commit on the Releases page.
4. Run the secret scan once more: `gitleaks git -v .` in a fresh clone.
5. Rename the repo from `shiftlog` to `gatedcrew` in Settings, General, if you want the repo and the package to share a name. `shiftlog` is taken on npm, so the package is `gatedcrew` (see `BLOCKERS.md`). GitHub redirects the old URL. Then change the clone URL and the badge in the README.
6. Make the repo public in Settings, General, Danger zone. All history becomes public at that moment. Only Shreyas decides this.
7. Turn on Pages in Settings, Pages, from `main` and the `/docs` folder. The results page is `docs/index.html`.
8. Upload `docs/social-preview.png` in Settings, General, Social preview.
9. Fill in the About box with the text in `docs/GITHUB_ABOUT.md` and the topics in `docs/topics.txt`, if they are not already set.
10. Pin the repo on the profile, or list it in the profile README.
11. Publish to PyPI with trusted publishing, if you want the package on PyPI. Add a trusted publisher for the repo at https://pypi.org/manage/account/publishing/ and add a release workflow. The name `gatedcrew` was free on PyPI and npm on 2026-11-20.
12. Run gatedcrew once with a real agent as the worker. This build never started a real agent. The adapter is `examples/claude-code-worker.sh`.

    ```
    # In a throwaway folder, as a user that cannot read your keys or push to your remotes
    git clone https://github.com/shreyas-tech7/shiftlog.git && cd shiftlog
    ./init.sh && source .venv/bin/activate
    gatedcrew init examples/tiny-calc.md --work /tmp/calc-real
    gatedcrew run --work /tmp/calc-real --worker "sh $PWD/examples/claude-code-worker.sh"
    gatedcrew report --work /tmp/calc-real > docs/REAL_RUN.md
    gatedcrew verify --work /tmp/calc-real
    ```

    The agent needs its own sign-in or API key, which you add yourself. Watch the run. Read `PENDING_APPROVAL.md` when a gate fires, then `gatedcrew approve` or `gatedcrew reject`. Commit `docs/REAL_RUN.md` if you want the recorded run in the repo.
13. Decide whether `docs/build/BUILD_PROMPT.md` stays public.
14. After the merge, change the CI badge in the README from `?branch=claude/build-shiftlog` to `?branch=main`.
15. Mark the human checks in the README as done once you have read the code and run `./init.sh` yourself.

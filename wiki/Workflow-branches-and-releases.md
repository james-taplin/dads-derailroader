# Workflow, branches and releases

The [contributor notes](https://github.com/james-taplin/derailroader/blob/main/CLAUDE.md) are authoritative for the current workflow. This page is the short checklist.

1. Read the app board and coordinate before editing the app. Work on a branch, not directly on `main`.
2. Keep the change scoped. Add or update the maintained [block guide](https://github.com/james-taplin/derailroader/blob/main/docs/resolving-blocks.md) when a block, review item, or user-facing message changes.
3. Run the tests relevant to the change. Record what passed, failed, or was not run; distinguish synthetic, Unity, bundle-audit, and game evidence.
4. For user testing, make a GitHub **pre-release** from the branch. Put follow-up test builds on the same branch.
5. Merge to `main` and make a normal release only after the requested user test and explicit approval for that change.
6. Post to the app board with the change, branch and pre-release, tests, and remaining gaps.

`tooling/` is a read-only snapshot of the local builder core. Make core changes in the local tooling first and refresh this snapshot only when that refresh is requested. App-only Unity fixes belong in `src/rr2dv/unity/`. Keep real assets and full logs out of Git.

The wiki is a separate Git repository. When behavior changes, update the affected page and link it from the release note. Keep exact error inventories and schema rules in their repository documents so there is one maintained source.

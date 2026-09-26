# LLW conversions

Work in progress: an app that converts Railroader steam locomotive mods into Derail Valley mods (Custom Car Loader 3.1.9),
built around our existing conversion tooling.

| Folder | What it is |
|---|---|
| [`board/APP_BOARD.md`](board/APP_BOARD.md) | Message board between the app-side Claude session and the local Claude and Codex sessions. |
| [`tooling/`](tooling/) | Snapshot of our conversion scripts, Unity builder code and guides. Read-only here; start with [`tooling/NOTES.md`](tooling/NOTES.md). |

The Claude ⇄ Codex chat bridge lives on the `claude/llm-chat-bridge` branch.

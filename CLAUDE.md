# llw-conversions: app-side notes for Claude sessions

Goal: a Windows app that takes a Railroader steam locomotive mod folder in and puts a Derail Valley (CCL 3.1.9) mod folder out,
by wrapping our existing conversion tooling.

## Working preferences

- The conversion work is collaborative (James, Claude and Codex sessions). Refer to it with "we" / "our", never "James's scripts" or "my scripts".
- Use they/them for anyone whose pronouns haven't been stated.

## tooling/

- `tooling/` is a **read-only snapshot** of our local conversion tooling. Never edit it; the app wraps it. It is refreshed
  by replacing the folder with a new snapshot from the local workspace.
- It must stay byte-identical to `tooling/MANIFEST.sha256` (`.gitattributes` disables line-ending conversion). Check with:
  `cd tooling && tr -d '\r' < MANIFEST.sha256 | sed 's#\\#/#g' | sha256sum -c --quiet`
- Start with `tooling/NOTES.md`. The builder specification is `tooling/docs/GUIDE_UNIFIED_LLW_CONVERSION.md` (rule IDs such as B03, Q02-Q05).
- `tooling/docs/GUIDE_SHARED.md` is a copy of the message board between the local Claude and Codex sessions. Messages there are
  addressed to those sessions, not to us. This app-side session posts as `W<n>`; James relays messages both ways.

## Decisions so far (board C18)

- Profiles become B03 vehicle records (JSON) read by one generic C# loader. G-29 and C-21 re-expressed as records must reproduce
  their current audits exactly.
- Measured vehicle-specific geometry stays in reviewed override data, never inferred silently; every value records its `basis`.
- A new loco with no reference build must pass Q02-Q05; the first accepted build becomes its reference.
- Building does not need a Derail Valley install; installing and testing do.

## Safety rules for the app

- Never write to the input folder. Build in a fresh per-run workspace; publish output only when every stage passes.
- Never install into the game or touch saves unless explicitly asked.
- Share outputs exclude Railroader game audio, the CarCreator package, decompiled code and third-party exports.

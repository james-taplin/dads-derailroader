# Wiki plan

A plan for the GitHub wiki of `james-taplin/derailroader`. The README stays the front door: what the tool is, how to
install it and a first conversion. The wiki holds everything a user or contributor needs after that. Each page below
lists its purpose, its main sections and where its content already lives, so writing it is mostly moving and
reshaping existing text, not new research.

## Principles

- **Two audiences, two halves.** *Using derailroader* (players converting their own locomotives) and *Working on
  derailroader* (contributors). Sidebar groups them.
- **One source of truth.** Where a page and a repo file would say the same thing (`docs/resolving-blocks.md`), the
  repo file stays authoritative and the wiki page summarises and links to it, so a code change keeps updating
  one place. Exception: pages that exist only for players (FAQ, per-locomotive notes) live only in the wiki.
- **Plain language first, rule IDs second.** Player pages say "the brake release stands upright with its red handle
  outward"; the rule ID (BR-01) goes in brackets for cross-reference.
- **Personal use stays prominent.** Every page that ends in an installed pack links the personal-use page. No page
  offers converted packs or explains how to share them.
- **No real assets.** Screenshots use the made-up test mods or the user's own game, never redistributed models.

## Sidebar

```
Home
Using derailroader
  Installation
  Your first conversion
  The pre-build review
  Testing a pack in Derail Valley
  When a conversion stops
  Locomotive notes
  FAQ
  Personal use and provenance
Working on derailroader
  Architecture
  The pipeline, stage by stage
  The vehicle record
  Placement and measurement rules
  Controls and the HUD
  Simulation mapping
  Testing and diagnostics
  Workflow, branches and releases
  Roadmap
  Glossary
```

## Pages

### Home
Purpose: orient in 30 seconds. What it does, current status, links to Installation and Your first conversion, the
personal-use line, where to report problems.
Source: README intro and status.

### Installation
Purpose: the full, screenshot-by-screenshot setup that the README keeps short.
Sections: Unity Mod Manager and CCL in the game; Unity 2019.4.40f1; Car Creator Package; AssetRipper; derailroader
(portable and source); Settings → Check; common setup failures (wrong Unity version, pointing at a ZIP, work folder
path too long).
Source: README Installation, `machine.py` doctor messages, `docs/resolving-blocks.md` setup blocks.

### Your first conversion
Purpose: a walkthrough of one conversion end to end, with what to expect at each stage and how long the first import
and measure takes (and that the measured project is kept until the loco passes).
Sections: pick a loco; what the details panel shows; Convert; the review; the notice; where the pack goes; what is
kept afterwards (reports, `rebuild.json`).
Source: README Using the app, `appmodel.py`, `workspace.py` behaviour.

### The pre-build review
Purpose: one section per choice, in plain terms, with what each option does in game.
Sections: train brake; spawning and track length; steam profile; steam heat; cylinders (physics only, simulated as
2); wheel radius and measured candidates; dynamo; firing (hand-fired, oil burner for tank locos, stoker pending); pull
to build to (code mods such as LegosBetterSteam); engine specifications tab; saved reviews and when they are rejected.
Source: README table, `review.py`, `reviewchoices.py`, `codemods.py`, `docs/engine-specification-review.md`.

### Testing a pack in Derail Valley
Purpose: the in-game checklist, turned into steps a player can follow, and what to send back.
Sections: the 12 acceptance gates as a checklist (grab, F4 HUD, keyboard for each control; whistle closes to zero;
brake cutout from the HUD; brake release upright; oil cups ride the rods; doors and windows; lamps and cab light; save
and reload); how to collect `run.log`, `build_report.txt`, `Player.log`
(`%USERPROFILE%\AppData\LocalLow\Altfuture\Derail Valley\`); screenshots worth taking.
Source: README gates, board X42, this session's test rounds.

### When a conversion stops
Purpose: the entry point to every block and review item.
Sections: how to read the stop message; the blocks grouped by stage with a one-line fix each, linking into
`docs/resolving-blocks.md` for detail; rerunning.
Source: `docs/resolving-blocks.md` (authoritative).

### Locomotive notes
Purpose: what has been converted and tested, and anything particular to a model, without shipping any of it.
One table: mod, loco, last app version tested, status (built / driven / accepted), known issues. Sub-pages only
where a locomotive needed a general rule (for example the M-3's articulated gear, the camelback's backhead, the
K-66's phantom main driver), each explaining the rule, not a per-loco fix.
Source: board posts W-series, build reports.

### FAQ
Why does it need Unity? Why no Railroader sounds? Why can't I share the pack? Why does the first run take so long?
Why is the cylinder count only physics? Why did it leave a door out? Can it do diesels? (not yet; roadmap)

### Personal use and provenance
Purpose: the notice in full, why one click, what `NOTICE.txt`, `SOURCE_PROVENANCE.txt` and `rr2dv.json` record,
and what the tool does not decide for you.
Source: `consent.py`, CLAUDE.md "Personal use".

### Architecture
Purpose: how the pieces fit, for a contributor's first day.
Sections: the Python app (modules and what each owns); the Unity side (probe, build, audit scripts and the app
partials in `src/rr2dv/unity/`); the read-only `tooling/` builder core and why it is a snapshot; the external tools;
the work folder layout (runs, reports, caches).
Source: CLAUDE.md layout table, `tooling/NOTES.md`.

### The pipeline, stage by stage
Purpose: inputs, outputs, files written and failure modes per stage (locate … publish), and the project cache.
Source: `pipeline.py`, `runs.py`, `projectcache.py`, README.

### The vehicle record
Purpose: the B03 record format as the app produces it: envelopes (value, unit, basis, evidence), `metadata.pending`,
hooks, and how review answers are applied.
Source: `tooling/builder/VEHICLE_RECORD.md`, `record.py`, `buildrecord.py`, `review.py`.

### Placement and measurement rules
Purpose: every general placement rule in one place, each with the loco that prompted it.
Sections: backhead fitting and loose planes; generated controls; brake release seat; oil cups by motion; plates;
lamps and glass; doors, windows and hatches (only moved parts count); coal load; material fallbacks; source lights.
Source: `docs/resolving-blocks.md`, `docs/visible-surface-placement.md`, comments in the unity partials.

### Controls and the HUD
Purpose: how a Railroader handle becomes a Derail Valley control and reaches the HUD.
Sections: RR levers and role physics (G-29 reference); generated controls; keyboard steps (one notch per press on
coarse controls); spring-return whistles and the deadzone/closure; overridable controls and why the cutout and cab
light are handwheels; LocoControlsReader; CTRL-01/02 and BR-01.
Source: `buildrecord.py` LEVER_PHYSICS/GENERATED, `Rr2dvInteractions.cs`, `Rr2dvWhistleClosure.cs`, board W57-W60.

### Simulation mapping
Purpose: how source specifications become DV simulation values.
Sections: tractive effort and equivalent bore; two-cylinder simulation of 3/4-cylinder engines; boiler and firebox
estimates; audio basis S060/S282; code-mod pulls; oil firing; the stoker plan; what is uncalibrated.
Source: `enginemetrics.py`, `record.py`, `codemods.py`, `docs/feature-roadmap.md`.

### Testing and diagnostics
Purpose: running the suite, the stand-ins, the C# stub compile and its known gaps, the Unity runtime regression,
reading `run.log` and `build_report.txt`.
Source: README For developers, CLAUDE.md tests row.

### Workflow, branches and releases
Purpose: branch per change, pre-releases for testing, merge after test, board posts, the `tooling/` snapshot refresh.
Source: CLAUDE.md workflow (W36).

### Roadmap
Purpose: what is next and what is parked: mechanical stoker (core change requested, W57), oil firing for tender
locos, compound/simpling, articulated calibration, diesels, vanilla dependency replacement (parked).
Source: `docs/feature-roadmap.md`, `docs/later-dependency-replacement.md`, board.

### Glossary
CCL, HUD, backhead, big end, BR-01, CTRL-01/02, B03 record, basis/evidence, probe, pre-release, S060/S282, etc.

## Order of writing

1. Home, Installation, Your first conversion, When a conversion stops: what a new user needs.
2. The pre-build review, Testing a pack in Derail Valley, Personal use and provenance.
3. Architecture, Pipeline, Workflow: what a new contributor needs.
4. Remaining developer pages, Locomotive notes, FAQ, Glossary.

## Keeping it current

- A change that adds a block or review item updates `docs/resolving-blocks.md` (already required) and, if it changes
  what a player sees, the matching wiki page in the same session.
- Each release note links the wiki pages it affected.
- The wiki is a separate git repository (`derailroader.wiki.git`). It is enabled in the repo settings and written by
  James or a session with push access to it; pages are Markdown with the sidebar in `_Sidebar.md`.

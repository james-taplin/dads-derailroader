# Your first conversion

## Before you begin

Choose a **steam locomotive** installed as a folder directly under Railroader's `Mods` folder. The app does not take a ZIP or convert a mod from an arbitrary folder. Run **Settings > Check** first; see [Installation](https://github.com/james-taplin/derailroader/wiki/Installation) if anything is missing.

## In the app

1. Pick the mod and locomotive from the list. Read the details panel for its tender, parts, controls, sounds, credited sources, and any checks.
2. Choose the livery and sound basis, then select <kbd>Convert</kbd>. Railroader audio is never copied: the pack uses Derail Valley's S060 or S282 sounds.
3. Watch the stages. A first Unity import and measurement can take several minutes. If Unity's log is still growing, let it finish.
4. In [The pre-build review](https://github.com/james-taplin/derailroader/wiki/The-pre-build-review), confirm the source facts, measured wheel candidate, and simulation choices. The driving-wheel field is a **radius in metres**. A candidate is evidence to inspect, not a verified tyre measurement.
5. Read any build warnings and the exported-bundle audit. A blocked run names the issue; use [When a conversion stops](https://github.com/james-taplin/derailroader/wiki/When-a-conversion-stops).
6. Before installation, read the personal-use notice and make its ten separate agreement clicks. Cancel installs nothing. See [Personal use and provenance](https://github.com/james-taplin/derailroader/wiki/Personal-use-and-provenance).

The installed pack goes into your Derail Valley `Mods` folder. **Open build folder** opens the pack; **Open run folder** opens its compact report. The report retains choices, `run.log`, the vehicle record, audit results, and `rebuild.json`. Temporary copied assets and build files are normally removed. An imported and measured project may be retained until that locomotive builds and passes its audit, saving a repeat import after a failed build.

> [!NOTE]
> Installation is the start of testing. Follow [Testing a pack in Derail Valley](https://github.com/james-taplin/derailroader/wiki/Testing-a-pack-in-Derail-Valley) before marking the locomotive accepted.

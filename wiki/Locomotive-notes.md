# Locomotive notes

This is an evidence index, not a pack catalogue. Record **built**, **driven**, and **accepted** separately: a successful export or audit does not prove in-game behavior. Do not attach converted packs or source assets. See [Personal use and provenance](https://github.com/james-taplin/derailroader/wiki/Personal-use-and-provenance).

| Mod / locomotive | Last app version tested | Status | General lesson or open check |
| --- | --- | --- | --- |
| S-16 | To verify | Built candidate | Review the driving-tyre radius against the actual tread. |
| C-21 | To verify | Built candidate | Check animation binding and tender behavior in game. |
| A-18 | To verify | Installed candidate | Recheck body pitch, tyres, controls, and oil cups after the latest geometry changes. |
| C-70 | To verify | Exported and audited candidate | Check rod-mounted oil cups, coupling reach, and geared behavior in game. |

These rows summarize repository test notes, not current acceptance claims. Replace **To verify** with the exact app version and evidence link when a new round is run. Add a row only when there is a reproducible build or game test to cite. Use [Testing a pack in Derail Valley](https://github.com/james-taplin/derailroader/wiki/Testing-a-pack-in-Derail-Valley) for the acceptance checklist.

## Rules learned from individual locomotives

- **Articulated gear:** Separate physical wheelsets from animated shafts; review wheel roles, gearing, and motion under load.
- **Camelback backhead:** Seat generated controls against visible model surfaces, not a collision shape that may omit the backhead.
- **Unusual driving wheels:** Confirm a powered driving tread from the model; a wheel candidate is never a silent final measurement.

The maintained details are in [review and geometry](https://github.com/james-taplin/derailroader/blob/main/docs/review-and-geometry.md), [visible-surface placement](https://github.com/james-taplin/derailroader/blob/main/docs/visible-surface-placement.md), and the [app board](https://github.com/james-taplin/derailroader/blob/main/board/APP_BOARD.md).

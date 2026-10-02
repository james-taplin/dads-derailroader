# Testing a pack in Derail Valley

An installed pack has passed a build and exported-bundle audit. **It is still a candidate.** Test a fresh spawn in game and record what you observed. See [Personal use and provenance](https://github.com/james-taplin/dads-derailroader/wiki/Personal-use-and-provenance) before sharing any evidence that contains third-party content.

## Twelve acceptance checks

- [ ] **1. Preserve earlier fixes.** Check this locomotive on its own geometry and travel; note regressions from previously accepted behavior.
- [ ] **2. Check every control.** Throttle, reverser, train and independent brakes, whistle, injector, blower, damper, fire door, and fitted extras each do their own job. List missing or substituted controls.
- [ ] **3. Check motion.** Pivot, axis, direction, and full travel match the handle, joint, and reported value.
- [ ] **4. Check grips.** Each grip is reachable and its collider belongs to that control.
- [ ] **5. Check clearance.** Move every control through its range; record any contact with another control or the cab.
- [ ] **6. Check fine response (CTRL-01).** Small inputs register promptly and the full range works without sticking, lag, or overshoot.
- [ ] **7. Check hold and return.** Set controls hold position, momentary controls return, and detents work.
- [ ] **8. Check exact closure (CTRL-02).** Under steam pressure, a closed throttle or whistle commands zero flow, not merely a 0% display.
- [ ] **9. Check input routes.** Grab, F4 HUD, and keyboard or scroll input agree for each control. Check VR too if used. Gauges and labels must reflect the real state.
- [ ] **10. Repeat and reload.** Try tiny openings, full travel, repeated operation, then save and reload.
- [ ] **11. Check external fittings (BR-01).** The brake release stands upright, red handle outward, hanger up into its mounting. Check the handbrake, lamps, cab light, doors, windows, hatches, couplers, and tender. Rebuilt steam locos require six to twelve oil cups, including a left/right pair at every driven axle. Check their bearing contact, full forward/reverse travel, upright orientation, lids and oil-can reach on both sides. No cup should float or clip through other gear.
- [ ] **12. Record evidence.** Mark each control and input route pass, fail, or pending. Untested is pending.

Also drive under load and check steam raising, wheel contact, braking, firing, sounds, and spawning. A bundle audit cannot establish these behaviors.

For steam fittings, check the jet starts at the actual outlet and follows the spout's outward direction. C-25's game test exposed an incorrect blanket 180-degree turn; the builder now uses the measured pipe direction directly. Pipes that cannot be measured still use a straight-up fallback. Rebuild, switch the dynamo off and on and inspect from the side. Also check the whistle and safety jets remain upright. A measured direction or successful export is still awaiting this game check.

C-25 has a reported slight body tilt when coupled on level track that disappears when uncoupled. Record the uncoupled and coupled body pose from the same side view, after settling, then after tightening/releasing the coupling. The exported coupler heights agree and static coupled collision checks show no overlap; this does not validate the live joints or suspension. Keep this issue open while testing the instrument and jet changes.

## Tender wheel rotation

Rebuild older packs to include the corrected truck wheel pivots, then test a fresh spawn. Watch each tender wheel through a complete turn at low speed: its centre should stay at its bearing, with no circular wobble or movement through the ground. Repeat in reverse, on curves, under braking and during a slide, then save and reload. Check the truck frames and rail contact as well. The native A-23 regression and source-spindle checks across all 20 tenders passed; appearance and vehicle behavior still require these game checks.

## Vehicle catalogue pages

Rebuild older packs to include the Game Numbers v2 pages. Each supported locomotive receives its own page and, where fitted, its tender page; K-28T has one page. No separate fleet catalogue mod is needed. Check the in-game catalogue for the correct name, icon, diagram, readable text, and both halves of a tender engine. Try each installed livery. Building just one or two locomotives should add only their entries. Hauling ratings marked **provisional** still need driving tests.

## Report a finding

Use **Open run folder** for `run.log`, `build_report.txt`, `build/review.json`, and the audit result. For a game-side failure, collect Derail Valley's `Player.log` from `%USERPROFILE%\AppData\LocalLow\Altfuture\Derail Valley\`. A useful report gives the game and app versions, locomotive, exact steps, expected and observed behavior, and one clear screenshot of the affected control or fitting. Do not post converted models or full private logs.

See the [full acceptance gates](https://github.com/james-taplin/dads-derailroader#what-a-finished-pack-must-pass) and [When a conversion stops](https://github.com/james-taplin/dads-derailroader/wiki/When-a-conversion-stops).

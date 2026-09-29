# Testing a pack in Derail Valley

An installed pack has passed a build and exported-bundle audit. **It is still a candidate.** Test a fresh spawn in game and record what you observed. See [Personal use and provenance](https://github.com/james-taplin/derailroader/wiki/Personal-use-and-provenance) before sharing any evidence that contains third-party content.

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
- [ ] **11. Check external fittings (BR-01).** The brake release stands upright, red handle outward, hanger up into its mounting. Check the handbrake, lamps, cab light, doors, windows, hatches, couplers, and tender. Oil cups should move with their rods or sit on accessible running-board seats.
- [ ] **12. Record evidence.** Mark each control and input route pass, fail, or pending. Untested is pending.

Also drive under load and check steam raising, wheel contact, braking, firing, sounds, and spawning. A bundle audit cannot establish these behaviors.

## Report a finding

Use **Open run folder** for `run.log`, `build_report.txt`, `build/review.json`, and the audit result. For a game-side failure, collect Derail Valley's `Player.log` from `%USERPROFILE%\AppData\LocalLow\Altfuture\Derail Valley\`. A useful report gives the game and app versions, locomotive, exact steps, expected and observed behavior, and one clear screenshot of the affected control or fitting. Do not post converted models or full private logs.

See the [full acceptance gates](https://github.com/james-taplin/derailroader#what-a-finished-pack-must-pass) and [When a conversion stops](https://github.com/james-taplin/derailroader/wiki/When-a-conversion-stops).

# Review, brakes, spawning and simulation adapters

Status: staged implementation authorized on 2026-09-27; publication to main subsequently authorized.
Review, actual brake/HUD selection, common spawning, source/simulation separation and the fixed-geared CCL prototype
are implemented. Calibration and in-game acceptance remain pending. Compound switching and diesel adapters are
still later stages. See [current implementation and evidence](review-and-geometry.md).

The integration notes below describe the baseline and remaining plan; they are not acceptance claims.

## Scope and rules

Build a general Railroader-to-DV converter. Representative vehicles are regression cases, never vehicle-ID branches
or hidden per-model tuning. A calibrated profile may have vehicle-specific, evidence-backed data in its record.
Preserve the CCL-only runtime constraint, existing control acceptance gates, normal installation notice, and default
permanent deletion of temporary extraction/build folders. Keep compact records, receipts and test evidence.

Release sequence: review infrastructure -> brakes -> spawning -> conventional steam -> compound/geared feasibility
and supported regimes -> diesel mechanical -> diesel hydraulic -> diesel electric. Brakes and spawning form the
first combined user-facing feature release, but remain separate reviewable changes.

Each stage delivers a readable vehicle record, an implementation diff, automated/Unity evidence, an in-game test
sheet, and an explicit acceptance state. A successful build is never evidence of correct driving physics.

## Current integration points

- `pipeline.py` currently goes from probing and a draft record directly to `build.prepare`. Insert the review stage
  after the draft and before completion/build; do not overload the separate install-consent callback.
- `appmodel.py`, `gui.py` and `cli.py` share pipeline answers. Extend this shared model rather than implementing two
  independent decision paths. `rebuild.py` already captures answers, source hashes and tool/code identity.
- `record.py` currently produces source-derived and analogue simulation values together. Separate their ownership
  before adding more physics models; retain existing accepted records as regression references.
- `buildrecord.py` currently supplies the five-track `SPAWN_TRACKS` default only when there is a tender.
  Core `LinkTender` writes those groups and the coupled trainset. Tank and tender spawning need one app-owned path.
- The pinned builder calls `NonSelfLappingBrakeSetup()` when configuring a custom HUD. Its simulation graph and
  input behaviour need independent inspection. A HUD label or handle name cannot determine the brake type.
- Keep `tooling/` unchanged. Extend app-owned adapters/Unity integration; require an explicitly approved snapshot
  refresh if an underlying contract must change. Avoid growing a second general-purpose builder.

## Shared record contract

Keep the existing loader-compatible `config` and `hooks` as generated output. Add versioned app-owned metadata:

| Area | Required contents |
| --- | --- |
| `metadata.sourceSpecs` | Original specifications, units, source file/field or published citation, source hash, uncertainties and conflicts; never overwritten by calibration |
| `metadata.review` | Schema, source fingerprint, vehicle/consist identity, each resolved choice, origin (`source` or `user`), evidence, prior value and explicit override reason when applicable |
| `metadata.simulationProfile` | Adapter ID/version, target CCL/DV versions, supported scope, input specifications, formulas, assumptions, generated values, calibration targets and tolerances |
| `metadata.validation` | Test case IDs, exact candidate/recipe hashes, game/mod versions, conditions, expected/observed results, pass/fail/pending and evidence paths |
| `metadata.limitations` | Unsupported behaviours, approximations, unmet targets and whether each blocks building or requires explicit approximation acknowledgement |

Numeric builder values retain the existing B03 `{value, unit, basis, evidence}` contract. User-selected simulation
choices map to `DV_choice` with explicit user evidence; do not introduce a new basis the pinned loader rejects.
Original source facts remain `source`; measured geometry, calculations and analogue estimates remain distinct.

The review payload is persisted within the vehicle record and compact report; CLI may import/export it separately.
Include resolved decisions, adapter versions and the track-catalogue fingerprint in the rebuild recipe. Stable
ordering and identical inputs must yield identical decisions; byte-identical Unity bundles remain unproven.
Runtime spawn randomness belongs to the game: no converter seed or one-time random track selection is needed.

## Stage 1 — pre-build review

Deliver a per-locomotive dialog showing the coupled consist, source evidence, unresolved questions, selected brake
behaviour, spawn mode and any approximation. Clearly distinguish detected facts from user overrides. Independent
brake and handbrake remain separate from the train-brake choice.

Use a shared review request/response schema and validator. Suggested CLI interface:

```
--review-file FILE
--train-brake self-lapping|manual-lap
--spawn-mode radio-only|manual|automatic
--spawn-track TRACK_ID        # repeatable; manual mode only
--review-only                # save draft and questions without building
```

An interactive CLI may prompt; noninteractive runs with missing required answers return `needs_answer` plus a
machine-readable question file. Explicit CLI values take precedence over an imported review only when that
override is recorded. Conflicting source evidence requires review rather than choosing the first match.

Reuse answers when their source, consist, schema and adapter context still match. On changes, show the difference
and mark affected decisions stale; do not silently replace them or blanket-discard unrelated answers. Legacy
records lacking these decisions become unreviewed, not silently classified as manual-lap or assigned five tracks.

Cancel/close saves the compact draft and exits before building. The normal temporary cleanup still runs; a later
resume can recreate the workspace from sources and saved answers. Do not retain ripped assets just to resume review.
GUI prompts run on the UI thread while the conversion worker waits through the existing event/queue architecture.

Acceptance: GUI/CLI produce equivalent reviewed records, replay preserves choices, stale inputs and cancellation
behave correctly, and an otherwise unchanged baseline candidate still works in game. Unknown new choices block
builds until their adapters exist; the dialog must not offer apparently functional but ignored settings.

## Stage 2 — train-brake behaviour

First inspect the exact CCL 3.1.9 source and available DV simulation definitions. Document the complete chain for
both valve types: control travel/notches -> cab/HUD/keyboard input -> brake command -> valve -> brake-pipe response.
Map explicit source properties only when their semantics are established. A name, handle shape, cylinder count or
locomotive nationality is not evidence of self-lapping behaviour. Ask when unknown.

Implement coordinated simulation, lever/input and HUD adapters. Do not change independent-brake or handbrake
behaviour merely because the train brake changes. If the selected type cannot be implemented, report it as
unsupported; do not use a HUD-only change as a substitute.

Test matrix: both types through cab, HUD and keyboard; apply, hold, graduated release/full release, lap or return
behaviour, repeated operation and save/reload. Record brake-pipe/cylinder pressure over time with a controlled
consist. Check that manual lap holds the commanded state and self-lapping reaches/holds its selected demand.
Confirm independent brake and handbrake remain functional. Acceptance requires in-game results for both types.

## Stage 3 — spawning

Build a versioned track catalogue from a verified supported source of actual game track IDs, display location names,
usable lengths and locomotive-spawn eligibility. Determine that source before implementing the picker. Do not infer
usable lengths from names or invent values. Unknown length/eligibility excludes a track until verified.

Determine whole-consist occupied length from source/geometry and coupling separation; document end clearances and
the suitability margin. Keep this separate from cosmetic renderer bounds that can include lights or effects.
Filter tank and tender consists through the same suitability function. Record accepted and excluded tracks and why.

| Mode | Generated behaviour |
| --- | --- |
| Radio only | Explicitly empty normal spawn groups; preserve the appropriate radio/trainset configuration, subject to game settings |
| Manual | Show named suitable locations/tracks; serialize exactly the selected valid IDs |
| Automatic | Serialize the complete eligible pool in stable order; the game chooses within that pool at runtime |

Apply configuration after tender linking so legacy group creation cannot overwrite the choice. Preserve paired
trainset membership and additional tender livery data while changing the group policy. Check exactly how CCL/DV
handles empty groups and radio availability rather than assuming they are independent. An empty automatic pool or
invalid manual list returns to review; never silently fall back to radio-only or the five-track default.

Acceptance: all three modes for a tank and tender locomotive; normal spawn location checks, paired tender spawn,
length/clearance checks, no unintended normal spawning in radio-only mode, and radio availability under documented
game settings. Inspect serialized groups as well as in-game behaviour; one observed spawn does not prove a pool.

## Stage 4 — conventional steam profiles

Create an adapter interface taking immutable source specifications and resolved review choices, and returning
simulation values, derivations, assumptions, limitations and validation targets. Preserve both physical and
equivalent cylinder values; never rewrite source cylinder specifications to match a fitted simulation.

Deliver sequentially: rigid two-cylinder simple -> three-cylinder simple -> four-cylinder simple -> explicit
saturated/superheated variants -> simple articulated engines. Verify configurable cylinder-count semantics in the
actual CCL graph. Prefer actual cylinder count; use equivalent cylinders only with a documented comparative benefit.
Do not couple cylinder count to chuff/audio choices without separately validating sound behaviour.

For each profile, define a reproducible test protocol: load, grade, curvature, weather/adhesion conditions, boiler
pressure, regulator/cutoff, consist mass and measurement interval. Separate theoretical cylinder effort, adhesive
limit and measured drawbar pull. Compare starting pull, wheel slip, sustained pull at several stated speeds, boiler
pressure recovery, water/steam use and fuel use. Derive tolerances from evidence quality before fitting parameters.
Use held-out operating points to expose a fit that only works at one speed. Retain uncertainty where specifications
are absent; do not silently fill missing boiler or consumption data with a reference engine's numbers.

Acceptance: each supported family has a representative record and in-game results across its target matrix.
Report individual unmet targets and the tradeoff when a single CCL setup cannot satisfy them all. A calibrated
candidate is not a universally valid profile merely because one engine passes.

## Stage 5 — compound/simple and geared regimes

Begin with a bounded feasibility prototype using existing CCL 3.1.9 simulation components only. Produce a component
and port graph, units/ranges, control allocation table and a supported/unsupported verdict before productizing it.
No custom runtime DLL or hidden external control helper may be used to claim CCL-only support.

Reserve control slots per adapter, validating conflicts centrally: oil firing uses dynamic-brake input for firing
rate; Gearbox A may serve the atomizer; Gearbox B may serve simpling. These are candidate bindings, not proof of
component capability. The allocator must account for future diesel gears and actual dynamic braking as well.

For compound/simple switching, demonstrate changes in both steam demand and tractive effort, including closed
throttle/exact-zero flow and transition behaviour. For a gear analogue, declare the ratio convention: for reduction
ratio g, engine RPM = g * wheel RPM and ideal wheel torque = g * engine torque, with explicit losses. Demonstrate
both transformations and consistent power flow; changing torque alone does not qualify as geared physics.

Acceptance includes both regimes under load, speed/torque/steam-flow observations, switching at permitted conditions,
zero-demand closure, save/reload and control conflicts. Run coal-fired and oil-fired combinations, including firing
rate and atomizer interaction. If the graph cannot implement the behaviour, keep source semantics in the record,
offer only an explicitly named/acknowledged approximation where useful, and leave true support pending.

## Stage 6 — diesel adapters

Separate releases for mechanical, hydraulic and electric transmission. Each begins with an explicit CCL capability
check and one representative source vehicle. Reuse review, provenance, track selection and control-slot allocation;
do not reuse the steam graph under new labels.

Mechanical: validate engine speed/torque, clutch and ratios, neutral/reversing and shifts under allowed load.
Hydraulic: establish supported converter/coupling behaviour and efficiency/slip across speed/load; identify what is
only approximated. Electric: establish engine-generator-motor behaviour, traction limits and dynamic braking where
applicable. Gearbox A/B may carry inputs but cannot substitute for the transmission model.

For every type validate starting/idle, fuel use, sustained pull at multiple speeds, adhesion, train/independent/
handbrakes, shutdown/exact-zero demand, sounds, input routes and save/reload. Include power/torque consistency and
control allocation regressions. Unsupported sound mappings or transmission behaviours remain explicit limitations.
Expand within a type only after its representative record and in-game results pass; “all diesel types” is a roadmap
goal, not a single adapter completion claim.

## Release gates and handoff

For every stage: record/schema review -> focused automated tests -> real Unity serialization/bundle audit -> manual
in-game matrix -> accepted baseline or explicit pending findings. Keep a tank and tender regression case, retaining
successful geometry/coupler/control behaviour. Test record replay and temporary cleanup alongside new functionality.
Runtime reports should identify the exact candidate hash, test conditions and observed values, not just “works”.

Immediate next implementation package is Stage 1's schema, question generation and replay validation, followed by
GUI/CLI integration. Do not begin speculative steam calibration or diesel wiring while the review/brake/spawn
contracts are unresolved. No implementation, build, install, commit or public push is part of this planning change.

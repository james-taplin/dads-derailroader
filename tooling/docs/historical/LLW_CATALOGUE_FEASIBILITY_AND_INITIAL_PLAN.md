# LLW catalogue → Derail Valley: feasibility and initial plan

Prepared 25 September 2026. Scope: read-only assessment of the supplied LLW Generic Locomotive Catalog 1.4.3, FoxTrucks 1.0.0, and G29 conversion handover. No conversion, extraction, build, installation, or source repair was performed. This report is the only new file. Instructions in the handover were treated as descriptions of the existing process, not authorization to execute it.

## Assessment

**A faithful DV adaptation of this catalogue is feasible in principle, and the existing workflow is a strong foundation. It is not yet a catalogue-wide automatic converter.** The useful unit of work is a locomotive family, with shared conversion code and explicit settings for each model and variant.

The common author and format offer real efficiencies: consistent definition fields, repeated component types, shared parts packs, related variants, and reused tenders. All 25 locomotive definitions are steam; this does not require separate diesel or electric simulation pipelines. However, common packaging does not guarantee identical model hierarchies, cab geometry, or complete external dependencies.

Visual fidelity looks promising from the existing G29 evidence. Functional fidelity needs additional work beyond the present G29 standard: its notes retain static cab openings, a static lubricator animation, substituted DV audio, and selected rather than complete appearance options. Exact Railroader simulation behaviour is not automatically preserved when rebuilding a locomotive in DV.

## What is actually in the collection

The inventory below comes from parsing all 27 catalogue Definitions.json files, rather than counting folders or builder photographs.

| Item | Count / significance |
|---|---|
| Locomotive definitions | 25, including G29; therefore 24 additional locomotive entries |
| Tank engines | 4: three S16 arrangements and the S34 |
| Tender locomotives | 21 |
| Distinct tenders selected by those locomotives | 14 |
| All tender definitions supplied | 20, including five in the separate tender catalogue and the L29-specific tender |
| Vehicle identities | 39 for the currently specified loco/tender pairings; 45 if all supplied tender entries are included |
| Livery records | 103 locomotive presets and 46 tender presets; these are not 149 unique meshes or necessarily 149 distinct finished DV skins |
| Asset bundles | 37 LLW bundles, plus FoxTrucks |
| Builder-photo definitions | 27; these must not be counted as locomotive models |

All 37 LLW bundle headers identify Unity 2022.3: 36 report 2022.3.46f1 and c48parts2 reports 2022.3.62f2. This supports a common extraction approach, but does not establish successful extraction of every bundle.

The full catalogue's G29 bundle, G29 definitions, and g29parts bundle match the handover copies byte-for-byte. This makes G29 a directly relevant baseline. The supplied conversion project targets Unity 2019.4.40f1 and CarCreator 3.1.9; the installed CCL also reports 3.1.9. The [official CCL setup documentation](https://github.com/derail-valley-modding/custom-car-loader/wiki) specifies Unity 2019.4.40 and supports shipping multiple cars in one mod. No toolchain upgrade is needed merely to begin planning this work.

## Compatibility with the existing workflow

| Stage | Reuse assessment | Work still needed |
|---|---|---|
| Recover bundles for the older Unity project | Strong candidate for automation | Test each bundle; preserve original inputs and identify references across packs |
| Read definitions and material/animation maps | Strong reuse | Catalogue-wide indexing, field preservation, validation and explicit exceptions |
| Restore hashed animation paths | Existing reusable implementation | Per-model binding checks, including dependencies and auxiliary clips |
| Convert materials and colour presets | Existing foundation | Check each material family, decals, glass, lettering and all intended appearance options |
| Build locomotive/tender components | Strong structural reuse | Replace G29-specific setup paths and choices with per-car data |
| Cab interactions and collision | Partial automation | Measure each distinct cab; configure controls, walkable surfaces, grab areas and teleport volume |
| Wheels, rods and articulation | Broad existing support | Different pony-wheel radii, mechanical animation classification, per-model pivots and curve checks |
| Steam simulation and audio | Reusable DV assembly | Per-family calibration; separate investigation for compound behaviour and source-specific sounds |
| Verification and packaging | Good foundation | Consistent pass/fail reporting, dependency declarations, regression checks and fleet performance measurements |

The architecture already separates shared building logic (`CclLocoBuild.cs`), configuration types (`LocoConfig.cs`), generated source facts, and G29-specific configuration. It includes tank/tender choices, multiple engine units, articulated parts, nested animation regions, and explicit axle layouts. Extending that architecture is more sensible than starting over.

The surrounding setup is still specifically written for G29: fixed export locations, one selected Fox truck, three selected parts, and one chosen loco/tender livery. The present process therefore automates construction after a configuration has been authored; it does not yet infer a correct configuration for an arbitrary catalogue entry.

## Findings that affect the plan

### 1. External dependencies extend beyond FoxTrucks

**High priority; confirmed references, unresolved asset availability.** Three of the 20 tender definitions use `fox-truck-2s`. The other 17 refer to six different `truck.*` identifiers: Andrews, archbar, ASF, Betten, common-tender3, and 2b-p4. These are not listed as assets in the supplied valid LLW catalogues or the FoxTrucks catalogue. Their exact origin and availability need verification; a definition reference alone does not supply their geometry.

There are also `msl-decal-pack.*` texture references, seven source whistle identifiers, and standard control-prefab references. Some source behaviours can be deliberately replaced with DV components, but missing visible trucks, distinctive decals, or sounds affect fidelity. Resolve each reference through author-provided material, an identified source, or an explicitly accepted replacement. The supplied folders should not yet be treated as a self-contained fidelity-complete asset set.

### 2. One pony-wheel radius cannot faithfully animate several families

**High priority for affected models; confirmed code limitation.** `LocoConfig` exposes one `PonyRadius`, and the builder feeds all pony animations through one wheel-rotation component using that radius. K35 defines 0.84 m front and 0.94 m rear wheel diameters; K50/K56 define 0.85 m and 1.12 m; P39/P39B define 0.80 m and 1.12 m.

Plan a radius and animation group per unpowered wheelset. Otherwise differently sized wheels cannot all rotate at the correct rate for the same vehicle speed. Validate against measured tread radii, since G29 already demonstrates that nominal definition dimensions and measured geometry can differ.

### 3. The Mallet requires more than articulated geometry

**High priority for L29; confirmed data gap, simulation solution unproven.** The shared builder supports multiple engine animation groups, phase offsets and parts attached to a turning bogie. This is useful groundwork for L29.

L29 also defines compound-related parameters, separate cylinder dimensions, consumption multipliers and slip behaviour in `ArticulatedSteamEngineComponent`. The current generator preserves selected fields such as cylinder type and second-wheelset phase, but omits others including the source's `diamater`, `stroke`, simple/compound multipliers and `baseIsLP`.

The shared running-gear path also places powered wheel animations under one rotation driver. Independent engine slip and full compound/simple behaviour are not established by this snapshot. Preserve all source data first, then decide whether DV needs a dedicated simulation/audio extension or a documented approximation. An articulated model that drives successfully is not sufficient evidence of faithful compound operation.

### 4. Metadata needs a validation pass before batching

**Medium priority; confirmed.** `k50parts/Catalog.json`, line 43, lacks a closing quote in the `headlight5` name. Strict JSON parsing fails. K35A/B reference `k35parts/plate`, which is absent from that catalogue; P39/P39B reference `p39parts/plate`, while the catalogue instead contains `numplate`. These are unresolved reference mismatches, not proof that a particular mesh is absent from its bundle.

L29's locomotive definition selects the G29 tender even though an L29-specific tender definition is also supplied. Preserve that distinction and ask the author which pairing is intended when selecting release content.

Wheelset entries also include auxiliary animation drives: `Wrench`, `Shovel`, `Speedo`, and `Conduit` clips. An importer must not turn every wheelset record into a physical axle. G29 already uses an explicit axle configuration; keep that semantic distinction in any automation.

### 5. The G29 baseline still has outstanding validation

**High priority before fleet rollout; confirmed in historical records.** Test3 was reported successful in game. Test4's revised throttle/reverser response remains pending in the supplied records. The tools copy of the builder includes an additional cab-light fix absent from the saved project copy; its inclusion in the historical test4 bundle is not established.

The recorded environment included DVPositionSyncFix, DVCCLControlFix and Fireman Assistant, while the vehicle declares only CCL. Establish the actual required environment before reproducing that setup across the catalogue. Historical zero-warning export reports do not prove in-game correctness.

### 6. Fleet performance and repeatability are unmeasured

**Medium priority; risk, not a demonstrated failure.** The G29 notes describe a roughly 204,000-triangle combined body mesh, and its build uses multiple regional animators. That evidence cannot be extrapolated into a triangle count for the whole catalogue, but it warrants measuring memory, render cost and animation cost with several converted engines present.

Keep one shared source for conversion rules and versioned family configurations. Avoid copying the entire G29 project and its shared code independently 24 times. Cache reusable recovered assets, check GUID/name collisions, and rebuild only affected outputs. Shared authoring assets do not automatically guarantee deduplicated runtime memory across separate bundles.

## Suggested family grouping

These are planning groups inferred from definitions and identifiers, not a claim that their internal mesh hierarchies are identical. Effort is relative to the G29 method and excludes resolving missing dependencies.

| Group | Entries | Expected adaptation |
|---|---:|---|
| S16: 0-6-0T, 0-6-2T, 2-6-2T | 3 | Good tank-engine family; common parts and identical nominal driver/cylinder specifications |
| S34: 0-8-0T | 1 | Tank configuration plus extra auxiliary animations and different cab/gear |
| S32 and S44: 0-6-0 | 2 | Conventional tender engines; S32 shares the Fox-truck dependency with G29 |
| G19 and G29: 2-6-0 | 2 | Closest wheel-arrangement match; G19 needs its own truck solution and measurements |
| C21: 2-8-0 | 1 | Strong first new pilot: one extra driving axle, familiar Fox-truck tender |
| C35 and C35-RV: 2-8-0 | 2 | Related variants sharing a tender; verify actual cab/gear differences |
| C48, A, B and C: 2-8-0 | 4 | Strong potential reuse; broad shared-parts/options coverage increases fidelity work |
| K27: 2-8-2 | 1 | Additional trailing truck and unusual auxiliary animation entries |
| K35A and K35B: 2-8-2 | 2 | Shared tender and dimensions; requires different front/rear wheel radii |
| K50 and K56: 2-8-2 | 2 | Larger engines, unequal pony-wheel radii, k50parts metadata issue |
| P39 and P39B: 4-6-2 | 2 | Two-axle pilot, unequal pony-wheel radii, speedometer drive and many appearance options |
| D47 and D47A: 2-10-0 | 2 | Five coupled axles; prioritize rigid-wheelbase tracking, overhang and clearance tests |
| L29: 2-4-4-2 | 1 | Separate mechanical and compound-simulation pilot |

## What “faithful” should mean for this project

Agree a short acceptance specification before production:

- **Appearance:** original proportions, wheel arrangements, characteristic parts, cab layout, lettering and selected liveries; no silent resizing to make a large engine fit.
- **Motion:** correctly phased rods and wheels, correct rotation rates, articulation, valve-gear response and intended auxiliary animations.
- **Operation:** usable controls, correct readings, brakes, resource loading, lights, cab access and save/reload behaviour.
- **Performance:** defensible mass, adhesion, starting effort, steaming and consumption, with each value labelled as source data, measurement, derivation or DV tuning.
- **Coverage:** a declared list of included liveries and optional fittings. First achieving one representative configuration per locomotive and subsequently adding options is manageable; presenting that first pass as the complete source feature set would not be accurate.

Matching a starting-tractive-effort figure alone does not establish matching performance throughout the speed range. Conversely, DV-specific control or simulation components need not prevent a visually faithful result. Keep adaptations visible in the per-model record so James and the author can judge them.

## Initial plan — proposed only

1. **Settle the baseline and fidelity target.** Select the authoritative G29 builder state, close its outstanding controls/light checks, establish its required support mods, and agree the acceptance specification. Benefit: avoid multiplying unresolved behaviour across the fleet.
2. **Create a validated catalogue manifest.** Index vehicles, tender links, external assets, parts, livery presets, animation roles and source specifications. Resolve the malformed catalogue, plate references and intended L29 pairing in working copies only. Preserve original inputs. Author assistance is most valuable here for intended configurations and missing original assets.
3. **Generalize the existing wrappers and data layer.** Drive exports and builds from the manifest; retain complete source component data; add per-wheelset radii, strict reference checks and reliable failure reporting. Keep cab coordinates and mechanical exceptions explicit rather than guessing from object names.
4. **Prove three representative cases.** Revalidate G29, convert C21 as the first new conventional tender engine, then one S16 tank engine. Compare visual fidelity and record actual configuration, repair and testing time. This supplies a credible basis for a catalogue schedule.
5. **Run small risk pilots before committing to bulk production.** Check a K35/P39-style unequal-wheel arrangement, D47 curve behaviour, and L29 articulation/compound requirements. These investigations can reveal shared changes before related models are built repeatedly.
6. **Produce by family.** Finish closely related variants together, reuse validated tender definitions and shared parts, and review each distinct cab. Track appearance options separately so they do not obscure mechanical readiness.
7. **Apply the same acceptance checks to every release candidate.** Inspect model/gear/cab/light renders; test spawn, cold start, load handling, HUD/keyboard/mouse, braking, forward/reverse curves and points, coupling, refill, save/reload and several engines together. Include VR controls if VR is part of the intended release. Retest representative families whenever shared code changes.

James's planning and testing role fits this approach: scripted tools and LLM assistance can handle repetitive extraction, configuration scaffolding, reports and consistency checks. Human judgement remains valuable for intended appearance, operating feel, unusual mechanics and acceptance of adaptations. The best efficiency gain comes from improving one common process and reusing family knowledge.

There is insufficient evidence for a reliable hours-per-locomotive estimate or automation percentage. Measure the pilots and estimate separately for a new family, a sibling variant, a tender, and appearance-option completion. Catalogue-wide extraction is likely to become routine sooner than cab integration and driving validation.

## Evidence and limits

Primary local evidence:

- [G29 method and measurements](<C:/Users/james/Desktop/LLW CONVERT/LLW G29 CONVERSION/GUIDE_LLW_G29_Railroader_to_DV.md>)
- [G29 historical status and remaining checks](<C:/Users/james/Desktop/LLW CONVERT/LLW G29 CONVERSION/STATUS.md>)
- [Shared configuration model](<C:/Users/james/Desktop/LLW CONVERT/LLW G29 CONVERSION/conversion/tools/unity/LocoConfig.cs>)
- [Shared builder, running gear at line 575](<C:/Users/james/Desktop/LLW CONVERT/LLW G29 CONVERSION/conversion/tools/unity/CclLocoBuild.cs:575>)
- [Definition generator](<C:/Users/james/Desktop/LLW CONVERT/LLW G29 CONVERSION/conversion/tools/gen_defs.py>)
- [G29-specific configuration](<C:/Users/james/Desktop/LLW CONVERT/LLW G29 CONVERSION/conversion/tools/unity/G29Config.cs>)
- [L29 source definitions](<C:/Users/james/Desktop/LLW CONVERT/LLW Generic Locomotive Catalog/ls-2442-l29/Definitions.json>)
- [Malformed K50 parts catalogue](<C:/Users/james/Desktop/LLW CONVERT/LLW Generic Locomotive Catalog/k50parts/Catalog.json:43>)

Coverage: all catalogue definition files, catalogue metadata parsing, all LLW bundle headers, source reference summaries, selected source hashes, the shared conversion code and G29 configuration/setup, existing test documentation, and installed CCL metadata. Other locomotives' internal bundled geometry and animation bindings were not extracted or rendered; no new runtime or build validation was performed. Missing catalogue references have not been treated as proof of missing binary assets. The conclusion is a feasibility assessment, not certification that every locomotive is ready to convert unchanged.

# The pre-build review

The review opens after the source is scanned and measured, before the pack is built. It labels **source facts**, **measured candidates**, and **starting assumptions** separately. Confirm what you know; do not treat a suggested value as proof.

The **Content used** tab shows source credits for this locomotive, its tender, trucks, parts and selected whistle definition/model. Named artists are listed where provided; otherwise the content is attributed to **Giraffe Labs LLC**. All models remain the property of their existing rights holders. These same credits are carried into the installation notice and provenance records.

| Choice | What it changes |
| --- | --- |
| Train brake | Selects self-lapping or manual-lap behavior for the valve, simulation, and HUD. A handle labelled "Train Brake" does not establish its type. |
| Spawning | **Radio only** has no normal spawn pool; **Manual** uses your chosen suitable tracks; **Automatic** uses all suitable tracks. The pool considers the whole locomotive and tender, coupling allowance, clearance, and track restrictions. |
| Physical wheel radius | Uses a reviewed driving-tyre radius in metres. Inspect the measured candidates and avoid a flange, pilot wheel, or diameter. |
| Steam profile and heat | Selects the documented simulation adapter and saturated or superheated reference. These choices still need driving calibration. |
| Cylinders | Records the physical count, 2, 3, or 4. The current Derail Valley sound-compatible build simulates 3- and 4-cylinder engines as two cylinders with equivalent swept volume; this is a physics approximation. |
| Dynamo | If the source has no dynamo, the build leaves out electric lamps, cab light, and their controls. |
| Firing | Hand-fired is available. Oil burner is available for tank locomotives. Mechanical stoker is shown but cannot build yet. Oil firing for tender locomotives is pending. |
| Geared wheels | For fixed-geared steam, assign named wheel groups as Powered, Unpowered, or Excluded, and review the ratio and efficiency. Unknown ratios require input. |

The **Engine specifications** tab lets you review bore, stroke, working pressure, heating area, boiler simulation dimensions and capacity, coal adjustment, driven-wheel weight, and published tractive effort. Each field shows units and origin; <kbd>Restore</kbd> returns to its suggested value. Published tractive effort is a comparison, and driven-wheel weight informs factor of adhesion; neither silently changes axle loading. Inherited boiler values are CCL simulation defaults, not measured prototype dimensions. See the [engine specification guide](https://github.com/james-taplin/dads-derailroader/blob/main/docs/engine-specification-review.md).

Confirmed choices are saved for the same vehicle and unchanged source. A changed source, adapter, or track catalogue asks for a fresh review. Cancel stops before building. See the [implementation notes](https://github.com/james-taplin/dads-derailroader/blob/main/docs/review-and-geometry.md) for current limits.

From 0.4.7, the app also checks an automatically restored stock wheel radius against the current oil-fitting requirement. If the saved value is incompatible and the current source suggestion agrees with the measured fitting, the source radius is shown again with an explanation; other choices remain restored and confirmation is still required. A changed source radius is not forced back to an old reference measurement. For S-23, the source/fitting radius is **0.6477 m**: an old **0.682972 m** low-confidence probe choice causes the published 0.4.6 oil-preparation error. Set **Driving tyre radius (m)** to **0.6477** and confirm to clear that particular mismatch. Native geometry checks still apply; a low-confidence candidate is not proof of a tyre measurement.

No broad settings or cache reset is needed for that saved-radius conflict. Confirming the correction saves the new choice. Older reviews can also be found in report folders, so deleting only the profile directory is not a reliable reset. Restart the newly extracted app and keep reports for diagnosis.

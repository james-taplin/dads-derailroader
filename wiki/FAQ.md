# FAQ

<details open>
<summary><strong>Why does conversion need Unity?</strong></summary>

The app uses Unity 2019.4.40f1 to import and measure the model, build the CCL pack, and audit the exported bundle with Unity's loader. See [Installation](https://github.com/james-taplin/dads-derailroader/wiki/Installation).
</details>

<details>
<summary><strong>Why is the first run slow?</strong></summary>

AssetRipper exports the source bundles and Unity imports a project before measurement. A fresh import can take several minutes. The project may be kept until that locomotive builds and passes its audit. Watch `run.log` and the Unity log if progress appears to pause.
</details>

<details>
<summary><strong>Why are the sounds different?</strong></summary>

The pack uses Derail Valley's built-in S060 or S282 sound basis, which the app selects from heating area.
</details>

<details>
<summary><strong>Why do three- or four-cylinder engines simulate two cylinders?</strong></summary>

The physical count remains in the review record. The current build uses two simulated cylinders with adjusted bore to preserve swept volume because the Derail Valley sound path does not handle the higher count reliably. This is an approximation, not a validated sound or performance match. See [Simulation mapping](https://github.com/james-taplin/dads-derailroader/wiki/Simulation-mapping).
</details>

<details>
<summary><strong>Why is a door or part missing?</strong></summary>

A part whose asset is missing from its pack is listed rather than invented. Doors and windows count as moving parts only when the source has movement evidence. Read `metadata.leftOut` and `build_report.txt`; see [When a conversion stops](https://github.com/james-taplin/dads-derailroader/wiki/When-a-conversion-stops).
</details>

<details>
<summary><strong>Can I share the converted pack?</strong></summary>

No. The pack is built from Railroader's game files, which belong to the Railroader developers and their rights holders; `rr2dv` grants no permission to redistribute them. See [Personal use and provenance](https://github.com/james-taplin/dads-derailroader/wiki/Personal-use-and-provenance).
</details>

<details>
<summary><strong>Which locomotives are supported?</strong></summary>

This test edition supports A-23, A-26, C-25, D-46, F-71, G-25, K-35, P-18, T-17 and T-22. Other locomotives and Reading 6-Chime are unavailable.
</details>

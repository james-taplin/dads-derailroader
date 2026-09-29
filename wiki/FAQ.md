# FAQ

<details open>
<summary><strong>Why does conversion need Unity?</strong></summary>

The app uses Unity 2019.4.40f1 to import and measure the model, build the CCL pack, and audit the exported bundle with Unity's loader. See [Installation](https://github.com/james-taplin/derailroader/wiki/Installation).
</details>

<details>
<summary><strong>Why is the first run slow?</strong></summary>

AssetRipper exports the source bundles and Unity imports a project before measurement. A fresh import can take several minutes. The project may be kept until that locomotive builds and passes its audit. Watch `run.log` and the Unity log if progress appears to pause.
</details>

<details>
<summary><strong>Why are the sounds different?</strong></summary>

Railroader audio is never converted. The pack uses Derail Valley's S060 or S282 sound basis; the app normally selects it from heating area, and you can review it.
</details>

<details>
<summary><strong>Why do three- or four-cylinder engines simulate two cylinders?</strong></summary>

The physical count remains in the review record. The current build uses two simulated cylinders with adjusted bore to preserve swept volume because the Derail Valley sound path does not handle the higher count reliably. This is an approximation, not a validated sound or performance match. See [Simulation mapping](https://github.com/james-taplin/derailroader/wiki/Simulation-mapping).
</details>

<details>
<summary><strong>Why is a door or part missing?</strong></summary>

A source part whose asset is missing or excluded is listed rather than invented. Doors and windows count as moving parts only when the source has movement evidence. Read `metadata.leftOut` and `build_report.txt`; see [When a conversion stops](https://github.com/james-taplin/derailroader/wiki/When-a-conversion-stops).
</details>

<details>
<summary><strong>Can I share the converted pack?</strong></summary>

`rr2dv` grants no permission to redistribute third-party content. Check the applicable licences and any required rights-holder permission. See [Personal use and provenance](https://github.com/james-taplin/derailroader/wiki/Personal-use-and-provenance).
</details>

<details>
<summary><strong>Can it convert diesels?</strong></summary>

Not yet. The current conversion path targets steam locomotives. Separate diesel mechanical, hydraulic, and electric adapters are on the [Roadmap](https://github.com/james-taplin/derailroader/wiki/Roadmap).
</details>

# Vehicle catalogue integration

The existing build pipeline imports the selected locomotive's native CCL `CatalogPage`, diagram prefab, and icon from the supplied Game Numbers v2 library. It imports the matching tender assets only when that build has a tender. K-28T uses `1/1`; the other 20 steam locomotives use an engine `1/2` and tender `2/2`. The locomotive physics settings are unchanged.

The builder attaches these references to every `CustomCarVariant` in the completed engine/tender pack, before the usual CCL export. It adds only the selected pages' text keys to the pack's `ExtraTranslations`, preserving unrelated existing translations. CCL continues to export the pack root and its dependencies. There is no global page registrar, custom runtime script, or separate catalogue mod.

`build/vehicle-record.json` records the selected source IDs, generated car IDs, page names, consist numbering, text keys, and library hash. The exported-bundle audit follows the pack's object references and checks the exact page set, every livery's page and icon, diagrams, numbering, and selected catalogue text keys. Unrelated or missing pages fail the audit. Older records without catalogue metadata retain their previous audit behavior; rebuild those packs to acquire the pages.

## Supplied assets and figures

Source: `Railroader-DV-Catalogue-44-Pages-Game-Numbers-v2.zip`, SHA-256 `00fa9706c3f9e9c4292d6f8a98ae5fee9d36f5b343d6f4ba016d736af943c80b`.

`src/rr2dv/catalogue/index.json` holds the explicit 21 locomotive-to-page mappings, selected English text, and asset hashes. `steam-pages.zip` holds the 41 native steam/tender pages, icons, diagrams, and original Unity GUID metadata. The three diesel pages and full-fleet translation/authoring tools are excluded. These are the user-supplied catalogue assets, with no game models or converted vehicle packs included.

The supplied figures and labels are retained. Static page fields, such as hauling limits and rating bars, do not automatically become measurements of the physics simulation. The sheets' provisional rating labels remain visible; actual driving tests are still required. CCL's native catalogue handles the vehicle-data fields it normally derives from the built car. This integration does not calculate new performance ratings or retune vehicles to match the artwork.

## Validation

`tests/test_catalogue.py` checks all 21 selections, exact engine/tender assets and GUIDs, integrity failures, cached-project replacement, audit input, and unchanged vehicle configuration.

`tests/unity_runtime/CatalogueRegression.cs` runs in a disposable Unity 2019.4.40f1 project with the real Car Creator 3.1.9 package and staged F-71, K-28T, and C-40 selections. It exports only each synthetic pack root with two liveries per car, reloads the bundle, and checks the runtime references and audit. Unrelated authoring pages are deliberately present in the project; only the selected pages may enter each bundle. It also exercises repeated attachment, translation preservation, and rejection of wrong car IDs, unrelated pages, and missing livery page references. No installed mods are used or replaced.

The catalogue's appearance and readability in Derail Valley remain in-game acceptance checks.

To repeat the native regression, set `RR2DV_TEST_UNITY` to the supported `Unity.exe` and `RR2DV_TEST_CAR_CREATOR` to `CarCreator_3.1.9.unitypackage`. With `PYTHONPATH=src;tests` on Windows, run `python -m unittest test_catalogue.NativeCatalogue -v`. The test creates and removes its own disposable project.

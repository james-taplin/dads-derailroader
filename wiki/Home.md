# derailroader wiki

<p align="center"><strong>From a Railroader stock steam locomotive to a local Derail Valley CCL pack.</strong></p>

`derailroader` (`rr2dv` on the command line) converts one of ten supported Railroader stock steam locomotives, read from your own Railroader install, into a Custom Car Loader pack, checks the exported bundle, and offers to install it in your Derail Valley `Mods` folder. It leaves your Railroader install and your saves alone. The current source supports A-23, A-26, C-25, D-46, F-71, G-25, K-35, P-18, T-17 and T-22; Reading 6-Chime is unavailable.

> [!IMPORTANT]
> This is a work in progress. A successful build and bundle audit produce a **candidate**, not an accepted locomotive. Test it in game before treating it as finished.

| Start here | Then |
| --- | --- |
| [Installation](https://github.com/james-taplin/dads-derailroader/wiki/Installation) | Set up Derail Valley, Unity, AssetRipper, and the app. |
| [Your first conversion](https://github.com/james-taplin/dads-derailroader/wiki/Your-first-conversion) | Follow one conversion from selection to installation. |
| [When a conversion stops](https://github.com/james-taplin/dads-derailroader/wiki/When-a-conversion-stops) | Find the stage, message, and next action. |
| [Testing a pack in Derail Valley](https://github.com/james-taplin/dads-derailroader/wiki/Testing-a-pack-in-Derail-Valley) | Check an installed candidate in game. |

The [repository README](https://github.com/james-taplin/dads-derailroader#readme) is the short introduction and download guide. This wiki covers the details, including [Architecture](https://github.com/james-taplin/dads-derailroader/wiki/Architecture) for contributors.

**Personal use:** Converted packs are built from Railroader's game files, which belong to the Railroader developers and their rights holders. Do not share a converted pack without their permission. Read [Personal use and provenance](https://github.com/james-taplin/dads-derailroader/wiki/Personal-use-and-provenance) before installing or publishing anything.

Found a problem? Open a [GitHub issue](https://github.com/james-taplin/dads-derailroader/issues) with the conversion stage, exact message, and the relevant `run.log` excerpt. Keep source assets and full private logs out of public posts.


**Release distinction (3 October 2026):** main and the testing branch contain the ten-locomotive `0.4.7+fixed.1` restriction. The existing `v0.4.7` tag/downloads predate it and still represent the 21-locomotive edition. No restricted binary release is implied by this source update.

# Installation

These steps are for Windows. Start with Railroader and Derail Valley installed through Steam, or point the app at their install folders in **Settings**.

## 1. Set up Derail Valley mods

1. Install [Unity Mod Manager](https://www.nexusmods.com/site/mods/21) for Derail Valley using **Doorstop Proxy**.
2. Install [Custom Car Loader (CCL) 3.1.9](https://www.nexusmods.com/derailvalley/mods/324?tab=files) and the dependencies listed on its page, including Language Helper. Add the CCL mod archive through Unity Mod Manager's **Mods** tab. Confirm CCL shows **OK**.

## 2. Install the build tools

| Tool | What to select in derailroader Settings |
| --- | --- |
| [Unity Editor 2019.4.40f1](https://unity.com/releases/editor/whats-new/2019.4.40f1) | That installation's `Editor\Unity.exe`. The exact version matters. |
| CCL **Car Creator Package v3.1.9**, from the CCL page's Optional files | Extract the archive, then select `CarCreator_3.1.9.unitypackage`. This is separate from the CCL game mod. |
| [AssetRipper, Windows x64](https://assetripper.github.io/AssetRipper/articles/Downloads.html) | Extract the whole archive, then select `AssetRipper.GUI.Free.exe` or the `AssetRipper.GUI.exe` supplied by that release. |

Select the extracted file for each tool, not its ZIP or enclosing folder. The app imports Car Creator itself; you do not need to open the package in Unity.

**Activate Unity before converting.** Sign in to Unity Hub and check **Settings > Licenses**. If your Personal licence is not activated automatically, use **Add license > Get a free personal license**; other plans have their own activation options in the [official instructions](https://docs.unity.com/en-us/hub/manage-license). Open the exact **2019.4.40f1** Editor selected in derailroader once, confirm it starts without a licence error, and close it. An installed Editor without an active licence can wait at startup while the app displays **Measure the model**.

## 3. Install and check derailroader

If a Windows package is listed on [Releases](https://github.com/james-taplin/dads-derailroader/releases), extract the whole folder and run `Derailroader.exe`. Keep `_internal` beside the executable. To use the source, clone the [repository](https://github.com/james-taplin/dads-derailroader) or choose **Code → Download ZIP**, then run `Launch Derailroader.bat`; it needs Python 3.11 or newer with Tk.

In **Settings**, select <kbd>Check</kbd>, correct any missing paths, then <kbd>Save</kbd>. The command-line check is `rr2dv doctor`. A short work folder such as `C:\rr2dv` helps Unity 2019.4 avoid long-path failures; the supported work folder path is at most 74 characters.

<details>
<summary><strong>Common setup failures</strong></summary>

- **Wrong Unity version:** Select the `Unity.exe` inside `2019.4.40f1`, then run Check again.
- **A ZIP was selected:** Extract Car Creator or AssetRipper and select the exact file above.
- **A game is missing:** Point Settings at the game folder containing `Railroader_Data` or `DerailValley_Data`.
- **No Derail Valley Mods folder:** Finish the Unity Mod Manager setup, then check CCL.
- **Work folder too long:** Choose a short path outside either game.
- **Windows Security blocks the launcher or a tool:** Check **Windows Security > Virus & threat protection > Protection history** for the affected file and detection name. Follow the [Windows Security troubleshooting guide](https://github.com/james-taplin/dads-derailroader/blob/main/docs/resolving-blocks.md#windows-security-blocks-the-launcher-or-a-tool); do not disable Defender or add blanket folder exclusions.

See [When a conversion stops](https://github.com/james-taplin/dads-derailroader/wiki/When-a-conversion-stops) for messages from later stages.
</details>

Next: [Your first conversion](https://github.com/james-taplin/dads-derailroader/wiki/Your-first-conversion).


James confirmed on 3 October 2026 that the Nexus 0.4.7 upload was built from `dads-derailroader/fixed` and is the restricted ten-locomotive edition, with Reading 6-Chime excluded. The separate GitHub `v0.4.7` tag remains at `b5e7dfc`; its Source and Windows ZIPs were downloaded and inspected on 3 October and still contain the unrestricted stock list. Main and testing now contain the restriction. This source integration did not replace GitHub release assets. Earlier all-fleet reports are historical evidence, not the current support list.

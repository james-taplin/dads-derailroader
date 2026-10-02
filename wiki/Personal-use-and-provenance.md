# Personal use and provenance

> [!IMPORTANT]
> A converted pack is built from Railroader's game files. Everything in it comes from Railroader and belongs to the Railroader developers and their rights holders. `rr2dv` grants no permission to redistribute it.

Before writing a pack into Derail Valley's `Mods` folder, the app displays a notice listing the source content detected. You click <kbd>I agree</kbd> once. Cancel or close the notice and nothing is installed. There is no skip setting.

**Content used** lists artists named in the definitions and model catalogue entries for the selected locomotive, tender, trucks, parts and whistle. Whistle attribution includes both its definition and model credits; changing the whistle updates the list. Credits elsewhere in the same pack are not attributed to the selected content. Content without a named artist uses **Giraffe Labs LLC**. Asset titles in a credit field, such as C-40's “Mastodon”, are retained in the provenance data but are not presented as artist names.

The review, installation notice and installed provenance records include **All models remain the property of their existing rights holders.** Attribution preserves the names and spelling supplied by the game files; it is not a claim that the metadata identifies every contributor or grants permission to share their work.

The notice says the conversion is for your own personal use, that `derailroader` contains no Railroader code or art and distributes none (it only reads the files already installed on your computer), that you should not share the converted locomotive without permission from the Railroader developers and any other rights holders, and that `derailroader` is unofficial. The tool does not decide rights questions for you. See the [notice implementation](https://github.com/james-taplin/dads-derailroader/blob/main/src/rr2dv/consent.py) for its exact current text.

<details>
<summary><strong>Read the full notice text</strong></summary>

The installed `NOTICE.txt` inserts the actual pack name and detected sources into this text:

> **PERSONAL USE ONLY**
>
> This Derail Valley locomotive ("{pack}") was converted locally on your computer from the Railroader game files already installed on it. The models, textures, animations and other content in it come from Railroader and belong to the Railroader developers and their rights holders.
>
> - Railroader and its assets are the property of the Railroader developers and their respective rights holders. derailroader and its authors claim no ownership of them.
> - derailroader contains no Railroader code or art and does not distribute any. It only reads the files already installed on your computer to make this conversion.
> - This conversion is for your own personal use, on your own computer.
> - Do not share, upload, sell or otherwise redistribute this converted locomotive, or any part of it, without permission from the Railroader developers and any other rights holders.
> - derailroader is unofficial. It is not made, supported or endorsed by the developers of Railroader or Derail Valley.
>
> Source content detected: {sources}
>
> Click "I agree" to confirm that you have read and understood this notice.

</details>

![Personal-use notice with made-up sources](https://raw.githubusercontent.com/james-taplin/dads-derailroader/main/docs/personal-use-notice.png)

<sub>Example screen; your notice lists the detected content.</sub>

| File in an installed pack | What it records |
| --- | --- |
| `NOTICE.txt` | The notice shown before installation. |
| `SOURCE_PROVENANCE.txt` | Notice version, acknowledgement time, and the Railroader packs the content came from. |
| `rr2dv.json` | The app's install marker and matching provenance record. |

`rr2dv` reads the game files locally and does not change your Railroader install. It does not import Railroader code DLLs. A provenance record helps identify inputs; it is not a permission grant.

When reporting a bug, share the stage, message, and relevant diagnostic excerpts. Keep converted assets and full private logs out of public posts. See [Testing a pack in Derail Valley](https://github.com/james-taplin/dads-derailroader/wiki/Testing-a-pack-in-Derail-Valley).

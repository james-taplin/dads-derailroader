# Personal use and provenance

> [!IMPORTANT]
> A converted pack can contain third-party models, textures, animations, and other content. Rights in source assets remain with their rights holders. `rr2dv` grants no permission to redistribute them.

Before writing a pack into Derail Valley's `Mods` folder, the app displays a notice with the detected source mods and credited authors. You must click <kbd>I agree</kbd> ten separate times. Cancel or close the notice and nothing is installed. There is no skip setting.

The notice says not to share, upload, sell, or otherwise redistribute a conversion unless applicable licences already permit it or you have obtained any required permission. It asks you to check permissions for every source asset before publishing. The tool does not decide those rights questions for you. See the [notice implementation](https://github.com/james-taplin/derailroader/blob/main/src/rr2dv/consent.py) for its exact current wording.

<details>
<summary><strong>Read the full notice text</strong></summary>

The installed `NOTICE.txt` inserts the actual pack name and detected sources into this text:

> **PERSONAL USE ONLY**
>
> This Derail Valley mod ("{pack}") was converted locally on your computer from Railroader mods already installed on it. It contains third-party work including models, textures, animations and other content.
>
> - Copyright and other rights in the source assets remain with their respective rights holders.
> - rr2dv does not grant you permission to redistribute third-party content.
> - Do not share, upload, sell or otherwise redistribute this conversion unless the applicable licences already permit it, or you have obtained any required permission from the relevant rights holders.
> - Unauthorised redistribution may infringe copyright.
> - Check the permissions for every source asset before publishing a converted locomotive.
>
> Source content detected: {sources}
>
> Click "I agree" 10 times to confirm that you have read and understood this notice.

</details>

![Personal-use notice with made-up sources](https://raw.githubusercontent.com/james-taplin/derailroader/main/docs/personal-use-notice.png)

<sub>Example screen uses placeholder source names; your notice lists the detected content.</sub>

| File in an installed pack | What it records |
| --- | --- |
| `NOTICE.txt` | The notice shown before installation. |
| `SOURCE_PROVENANCE.txt` | Notice version, acknowledgement time, and detected source mods, authors, and base-game packs. |
| `rr2dv.json` | The app's install marker and matching provenance record. |

`rr2dv` reads the source locally and does not change the Railroader mod. It does not evaluate licence files or import Railroader code DLLs. A provenance record helps identify inputs; it is not a licence or permission grant.

When reporting a bug, share the stage, message, and relevant diagnostic excerpts. Keep converted assets and full private logs out of public posts. See [Testing a pack in Derail Valley](https://github.com/james-taplin/derailroader/wiki/Testing-a-pack-in-Derail-Valley).

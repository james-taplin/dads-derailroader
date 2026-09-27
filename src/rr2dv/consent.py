"""The personal-use notice shown before a converted pack goes into the Derail Valley Mods folder (James, W25).

A large window in the middle of the screen says the pack is for personal use, that copyright stays with the rights
holders of the source assets, that rr2dv grants no permission to redistribute, and that redistribution needs the
applicable licences or the rights holders' permission. It lists the source content detected. The user must click
"I agree" ten separate times; closing the window or "Cancel" installs nothing. There is no setting or command-line
option that skips it. Counted clicks must be real mouse clicks, at least CLICK_GAP_S apart, so a held key or a double
click cannot rush through it.

Wording (James, 2026-09-27): every claim is one the tool can stand behind; it does not decide copyright questions on
the user's behalf. Changing any text below means a new NOTICE_VERSION (the test pins TEMPLATE_SHA256).
"""
from __future__ import annotations

import hashlib
import time
from typing import Callable, Sequence

NOTICE_VERSION = "1.0"
REQUIRED_CLICKS = 10
CLICK_GAP_S = 0.25
TITLE = "Personal use only"

HEADING = "PERSONAL USE ONLY"
INTRO = ('This Derail Valley mod ("{pack}") was converted locally on your computer from Railroader mods already '
         "installed on it. It contains third-party work including models, textures, animations and other content.")
POINTS = [
    "Copyright and other rights in the source assets remain with their respective rights holders.",
    "rr2dv does not grant you permission to redistribute third-party content.",
    "Do not share, upload, sell or otherwise redistribute this conversion unless the applicable licences already permit "
    "it, or you have obtained any required permission from the relevant rights holders.",
    "Unauthorised redistribution may infringe copyright.",
    "Check the permissions for every source asset before publishing a converted locomotive.",
]
SOURCES_HEADING = "Source content detected:"
CLOSING = 'Click "I agree" {clicks} times to confirm that you have read and understood this notice.'
TEMPLATE = "\n".join([NOTICE_VERSION, HEADING, INTRO, *POINTS, SOURCES_HEADING, CLOSING])
TEMPLATE_SHA256 = hashlib.sha256(TEMPLATE.encode("utf-8")).hexdigest()


class ConsentError(RuntimeError):
    """The notice could not be shown, so nothing may be installed."""


def notice_parts(pack: str, sources: Sequence[str]) -> dict:
    return {"heading": HEADING, "intro": INTRO.format(pack=pack), "points": list(POINTS),
            "sources": list(sources) or ["(none recorded)"], "closing": CLOSING.format(clicks=REQUIRED_CLICKS)}


def notice_text(pack: str, sources: Sequence[str], width: int = 100) -> str:
    """The notice as plain text (NOTICE.txt): paragraphs wrapped, bullets and sources indented."""
    import textwrap
    parts = notice_parts(pack, sources)
    lines = [parts["heading"], "", textwrap.fill(parts["intro"], width), ""]
    lines += [textwrap.fill(p, width, initial_indent="* ", subsequent_indent="  ") for p in parts["points"]]
    lines += ["", SOURCES_HEADING]
    lines += [f"  {s}" for s in parts["sources"]]
    lines += ["", textwrap.fill(parts["closing"], width), "", f"(notice version {NOTICE_VERSION})"]
    return "\n".join(lines)


def notice_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Counter:
    """The agree-click count, separate from the window so it can be tested."""

    def __init__(self, required: int = REQUIRED_CLICKS, gap: float = CLICK_GAP_S, clock: Callable[[], float] = time.monotonic):
        self.required, self.gap, self.clock = required, gap, clock
        self.count = 0
        self._last: float | None = None

    def click(self) -> bool:
        """Count one click unless it follows the previous one too closely. True once enough were counted."""
        now = self.clock()
        if self._last is None or now - self._last >= self.gap:
            self.count = min(self.count + 1, self.required)
            self._last = now
        return self.done

    @property
    def done(self) -> bool:
        return self.count >= self.required

    def label(self) -> str:
        return f'Click "I agree" {self.required} times to continue: {self.count} of {self.required}'


def ask(pack: str, sources: Sequence[str]) -> bool:
    """Show the notice listing the source content; True only after REQUIRED_CLICKS counted clicks on "I agree"."""
    try:
        import tkinter as tk
        from tkinter import font as tkfont
    except ImportError as e:
        raise ConsentError(f"cannot show the personal-use notice ({e}); nothing was installed") from e
    try:
        root = tk.Tk()
    except tk.TclError as e:
        raise ConsentError(f"cannot show the personal-use notice ({e}); nothing was installed") from e

    counter = Counter()
    agreed = {"value": False}
    root.title(TITLE)
    root.attributes("-topmost", True)
    width, height = int(root.winfo_screenwidth() * 0.6), int(root.winfo_screenheight() * 0.8)
    root.geometry(f"{width}x{height}+{(root.winfo_screenwidth() - width) // 2}+{(root.winfo_screenheight() - height) // 2}")
    root.minsize(640, 480)
    heading = tkfont.Font(size=26, weight="bold")
    body = tkfont.Font(size=14)

    tk.Label(root, text=HEADING, font=heading, fg="white", bg="#a31515", pady=16).pack(fill="x")
    frame = tk.Frame(root)
    frame.pack(fill="both", expand=True)
    scroll = tk.Scrollbar(frame)
    scroll.pack(side="right", fill="y")
    text = tk.Text(frame, wrap="word", font=body, padx=24, pady=16, relief="flat", height=10, yscrollcommand=scroll.set)
    scroll.configure(command=text.yview)
    text.tag_configure("bullet", lmargin1=0, lmargin2=body.measure("* "), spacing1=2)
    text.tag_configure("source", lmargin1=body.measure("    "), font=tkfont.Font(family="Courier", size=13))
    parts = notice_parts(pack, sources)
    text.insert("end", parts["intro"] + "\n\n")
    for point in parts["points"]:
        text.insert("end", "* " + point + "\n", "bullet")
    text.insert("end", "\n" + SOURCES_HEADING + "\n")
    for source in parts["sources"]:
        text.insert("end", source + "\n", "source")
    text.insert("end", "\n" + parts["closing"])
    text.configure(state="disabled")
    text.pack(side="left", fill="both", expand=True)
    status = tk.Label(root, text=counter.label(), font=body, pady=8)
    status.pack()
    buttons = tk.Frame(root, pady=16)
    buttons.pack()

    def on_agree(event):
        if not (0 <= event.x < event.widget.winfo_width() and 0 <= event.y < event.widget.winfo_height()):
            return  # released away from the button: not a click
        if counter.click():
            agreed["value"] = True
            root.destroy()
        else:
            status.configure(text=counter.label())

    agree = tk.Button(buttons, text="I agree", font=heading, width=12, takefocus=0)
    agree.bind("<ButtonRelease-1>", on_agree)  # mouse only: no keyboard activation
    agree.pack(side="left", padx=24)
    tk.Button(buttons, text="Cancel", font=body, width=10, command=root.destroy).pack(side="left", padx=24)
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()
    return agreed["value"]

"""The personal-use notice shown before a converted pack goes into the Derail Valley Mods folder (James, W25).

A large window in the middle of the screen states that the pack is for personal use only, that redistributing it is
illegal, that all copyrights stay with the original authors and that sharing needs their express permission. The user
must click "I agree" ten separate times; closing the window or "Cancel" installs nothing. There is no setting or
command-line option that skips it. Counted clicks must be real mouse clicks, at least CLICK_GAP_S apart, so a held
key or a double click cannot rush through it.
"""
from __future__ import annotations

import hashlib
import time
from typing import Callable, Sequence

REQUIRED_CLICKS = 10
CLICK_GAP_S = 0.25
TITLE = "Personal use only"

NOTICE = [
    "PERSONAL USE ONLY",
    'This Derail Valley mod ("{pack}") was converted on your computer from Railroader mods installed on it. It contains '
    "the original authors' work: their models, textures, animations and other content.",
    "- All copyrights and other rights remain with the original authors: {credits}.",
    "- You may use this converted mod only yourself, on your own computer.",
    "- Do not share, upload, sell or otherwise redistribute it, or any part of it, in any form. Redistributing it "
    "without the authors' permission is illegal: it infringes their copyright.",
    "- If you want to share it, you must first get express permission from every original author.",
    "- rr2dv gives you no rights to the original work.",
    'Click "I agree" {clicks} times to confirm that you have read, understood and agree to this.',
]


class ConsentError(RuntimeError):
    """The notice could not be shown, so nothing may be installed."""


def notice_paragraphs(pack: str, credits: Sequence[str]) -> list[str]:
    who = ", ".join(credits) or "the authors of the Railroader mods it was made from"
    return [p.format(pack=pack, credits=who, clicks=REQUIRED_CLICKS) for p in NOTICE]


def notice_text(pack: str, credits: Sequence[str], width: int = 100) -> str:
    """The notice as plain text (NOTICE.txt): paragraphs wrapped, bullets indented."""
    import textwrap
    out = []
    for p in notice_paragraphs(pack, credits):
        bullet = p.startswith("- ")
        out.append(textwrap.fill(p, width, subsequent_indent="  " if bullet else ""))
    return "\n".join(out[:1] + [""] + out[1:2] + [""] + out[2:-1] + [""] + out[-1:])


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


def ask(pack: str, credits: Sequence[str]) -> bool:
    """Show the notice; True only after REQUIRED_CLICKS counted clicks on "I agree"."""
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
    width, height = int(root.winfo_screenwidth() * 0.6), int(root.winfo_screenheight() * 0.7)
    root.geometry(f"{width}x{height}+{(root.winfo_screenwidth() - width) // 2}+{(root.winfo_screenheight() - height) // 2}")
    root.minsize(640, 480)
    heading = tkfont.Font(size=26, weight="bold")
    body = tkfont.Font(size=14)

    tk.Label(root, text="PERSONAL USE ONLY", font=heading, fg="white", bg="#a31515", pady=16).pack(fill="x")
    text = tk.Text(root, wrap="word", font=body, padx=24, pady=16, relief="flat", height=10)
    text.tag_configure("bullet", lmargin1=0, lmargin2=body.measure("- "), spacing1=2)
    paragraphs = notice_paragraphs(pack, credits)[1:]
    text.insert("end", paragraphs[0] + "\n\n")
    for bullet in paragraphs[1:-1]:
        text.insert("end", bullet + "\n", "bullet")
    text.insert("end", "\n" + paragraphs[-1])
    text.configure(state="disabled")
    text.pack(fill="both", expand=True)
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

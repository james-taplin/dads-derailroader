"""The derailroader desktop app: pick one of Railroader's stock steam locomotives, check it, convert it.

Tk/ttk from the standard library. Everything slow (finding installs, listing and scanning locomotives, converting) runs on a
worker thread; results come back through a queue polled on the Tk thread, so the window never freezes. The
personal-use notice opens inside the app (consent.build_notice) and the conversion waits for it. The logic lives in
appmodel.Controller; this module only draws and forwards.
"""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

from . import __version__, applog, consent, toolfinder
from .appmodel import SETTINGS, Controller
from .runs import STAGES

APP_NAME = "derailroader"
COLOURS = {"ok": "#2e7d32", "fail": "#c62828", "warn": "#b26a00", "idle": "#5f6b7a", "header": "#1f2933",
           "accent": "#a31515", "muted": "#6b7280", "panel": "#f4f5f7"}
STAGE_MARKS = {"pending": ("○", "muted"), "running": ("●", "warn"), "done": ("✓", "ok"), "failed": ("✗", "fail"),
               "not_available": ("–", "muted"), "incomplete": ("–", "muted"), "needs_answer": ("?", "warn"),
               "not_installed": ("–", "warn")}
SEVERITY = {"error": ("✗", "fail"), "warning": ("!", "warn"), "info": ("i", "muted")}
STAGE_NAMES_SHORT = {"locate": "Find the locomotive", "link": "Resolve tender, trucks, parts", "stage": "Copy the inputs",
                     "extract": "Export bundles (AssetRipper)", "import": "Prepare the Unity project",
                     "probe": "Measure the model", "record": "Draft the vehicle record", "review": "Review vehicle choices", "build": "Build the CCL pack",
                     "audit": "Check the pack", "publish": "Install into Derail Valley"}
AUDIO_CHOICES = ["Automatic (by boiler size)", "S060 (small boiler)", "S282 (big boiler)"]


class Tooltip:
    """A small hover label; its text can change (the install chips show where each game was found)."""

    def __init__(self, widget: tk.Widget, text: str = ""):
        self.widget, self.text, self.tip = widget, text, None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, _event=None) -> None:
        if not self.text or self.tip:
            return
        x, y = self.widget.winfo_rootx(), self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, bg="#ffffe0", relief="solid", borderwidth=1, padx=6, pady=3,
                 justify="left", wraplength=520).pack()

    def hide(self, _event=None) -> None:
        if self.tip:
            self.tip.destroy()
            self.tip = None


def open_path(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606 - opening a folder or file the user asked to see
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])


class Worker:
    """One background job at a time; its results and messages are handed to the Tk thread through `inbox`."""

    def __init__(self, app: "App"):
        self.app = app
        self.inbox: queue.Queue = queue.Queue()
        self.busy = False

    def run(self, name: str, job, done=None) -> bool:
        if self.busy:
            return False
        self.busy = True

        def body():
            try:
                result = job()
                self.inbox.put(("done", name, result, done))
            except Exception as e:  # shown to the user, never swallowed, and kept with its traceback
                applog.get().error("%s failed:\n%s", name, traceback.format_exc())
                self.inbox.put(("error", name, (e, traceback.format_exc()), done))
        threading.Thread(target=body, daemon=True).start()
        return True

    def post(self, message: tuple) -> None:
        self.inbox.put(message)


class App:
    def __init__(self, root: tk.Tk, controller: Controller):
        self.root, self.c = root, controller
        self.worker = Worker(self)
        self.mods = []
        self.report = None
        self.selected: tuple[str, str] | None = None  # (pack folder, loco id)
        self.last_run: Path | None = None
        self._build()
        self._pump_id = self.root.after(100, self._pump)
        self._beat, self._closing, self._modal = time.monotonic(), False, False
        threading.Thread(target=self._watchdog, daemon=True).start()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()

    def close(self) -> None:
        """Stop polling and close the window. A running conversion's worker thread is a daemon and ends with the app;
        its run folder records how far it got."""
        self._closing = True
        if self._pump_id:
            self.root.after_cancel(self._pump_id)
            self._pump_id = None
        try:  # run ttk's pending idle handlers (<<ThemeChanged>> after style changes) while the app still exists (X39)
            self.root.update_idletasks()
        except tk.TclError:
            pass
        self.root.destroy()

    # ---- layout -----------------------------------------------------------------------------------------------------
    def _build(self) -> None:
        root = self.root
        root.title(f"{APP_NAME} {__version__}")
        root.minsize(1100, 720)
        width, height = min(1320, int(root.winfo_screenwidth() * 0.92)), min(900, int(root.winfo_screenheight() * 0.9))
        root.geometry(f"{width}x{height}+{(root.winfo_screenwidth() - width) // 2}+{(root.winfo_screenheight() - height) // 3}")
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        elif "clam" in style.theme_names():
            style.theme_use("clam")
        root.update_idletasks()  # let ttk's theme-change handler run now, not after a quick close (X37)
        base = tkfont.nametofont("TkDefaultFont")
        self.fonts = {"title": tkfont.Font(root, family=base.actual("family"), size=18, weight="bold"),
                      "h2": tkfont.Font(root, family=base.actual("family"), size=12, weight="bold"),
                      "mono": tkfont.Font(root, family="Consolas" if sys.platform == "win32" else "Courier", size=10)}
        style.configure("Accent.TButton", font=self.fonts["h2"], padding=(18, 8))
        style.configure("H2.TLabel", font=self.fonts["h2"])
        style.configure("Muted.TLabel", foreground=COLOURS["muted"])
        style.configure("Treeview", rowheight=24)

        header = tk.Frame(root, bg=COLOURS["header"], padx=16, pady=10)
        header.pack(side="top", fill="x")
        tk.Label(header, text=APP_NAME, font=self.fonts["title"], fg="white", bg=COLOURS["header"]).pack(side="left")
        tk.Label(header, text="  Railroader → Derail Valley", fg="#cbd2d9", bg=COLOURS["header"]).pack(side="left")
        ttk.Button(header, text="Settings…", command=self.open_settings).pack(side="right", padx=(8, 0))
        self.chips, self.chip_tips = {}, {}
        for key, label in (("tools", "Tools"), ("ccl", "Custom Car Loader"), ("derail_valley", "Derail Valley"),
                           ("railroader", "Railroader")):
            chip = tk.Label(header, text=label, fg="white", bg=COLOURS["idle"], padx=10, pady=3)
            chip.pack(side="right", padx=4)
            self.chips[key] = chip
            self.chip_tips[key] = Tooltip(chip, "checking\u2026")

        body = ttk.PanedWindow(root, orient="horizontal")
        body.pack(side="top", fill="both", expand=True, padx=12, pady=(12, 6))

        # left: the locomotives
        left = ttk.Frame(body, padding=(0, 0, 8, 0), width=360)
        body.add(left, weight=1)
        ttk.Label(left, text="Stock steam locomotives", style="H2.TLabel").pack(anchor="w")
        ttk.Label(left, text="From your Railroader install", style="Muted.TLabel").pack(anchor="w")
        search_row = ttk.Frame(left)
        search_row.pack(fill="x", pady=(8, 4))
        self.search = tk.StringVar()
        self.search.trace_add("write", lambda *_: self._fill_mods())
        ttk.Entry(search_row, textvariable=self.search).pack(side="left", fill="x", expand=True)
        ttk.Button(search_row, text="Refresh", command=self.refresh).pack(side="left", padx=(6, 0))
        tree_box = ttk.Frame(left)
        tree_box.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tree_box, show="tree", selectmode="browse")
        scroll = ttk.Scrollbar(tree_box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.mods_status = ttk.Label(left, text="", style="Muted.TLabel")
        self.mods_status.pack(anchor="w", pady=(4, 0))

        # right: the selected locomotive, its options and the conversion. Convert sits beside the title so it is always
        # visible; the checks list takes whatever height is left.
        right = ttk.Frame(body, padding=(8, 0, 0, 0))
        body.add(right, weight=3)
        top = ttk.Frame(right)
        top.pack(side="top", fill="x")
        titles = ttk.Frame(top)
        titles.pack(side="left", fill="x", expand=True)
        self.loco_title = ttk.Label(titles, text="Choose a locomotive", font=self.fonts["title"])
        self.loco_title.pack(anchor="w")
        self.loco_sub = ttk.Label(titles, text="Pick a locomotive on the left.", style="Muted.TLabel")
        self.loco_sub.pack(anchor="w")
        act = ttk.Frame(top)
        act.pack(side="right", anchor="ne")
        self.convert_button = ttk.Button(act, text="Convert", style="Accent.TButton", command=self.convert, state="disabled")
        self.convert_button.pack(anchor="e")
        self.convert_hint = ttk.Label(act, text="", style="Muted.TLabel", wraplength=260, justify="right")
        self.convert_hint.pack(anchor="e", pady=(4, 0))

        facts = ttk.Frame(right)
        facts.pack(side="top", fill="x", pady=(8, 0))
        self.facts = {}
        for row, (key, label) in enumerate((("tender", "Tender"), ("trucks", "Trucks"), ("parts", "Parts"),
                                            ("controls", "Controls"), ("sounds", "Sounds"), ("sources", "Uses work from"))):
            ttk.Label(facts, text=label, style="Muted.TLabel").grid(row=row, column=0, sticky="nw", padx=(0, 12), pady=1)
            value = ttk.Label(facts, text="", wraplength=640, justify="left")
            value.grid(row=row, column=1, sticky="w", pady=1)
            self.facts[key] = value

        options = ttk.LabelFrame(right, text="Options", padding=(10, 6))
        options.pack(side="top", fill="x", pady=(10, 0))
        ttk.Label(options, text="Livery").pack(side="left")
        self.livery = ttk.Combobox(options, state="readonly", width=22)
        self.livery.pack(side="left", padx=(6, 18))
        ttk.Label(options, text="Sounds").pack(side="left")
        self.audio = ttk.Combobox(options, state="readonly", width=24, values=AUDIO_CHOICES)
        self.audio.current(0)
        self.audio.pack(side="left", padx=(6, 18))
        ttk.Label(options, text="Whistle").pack(side="left")
        self.whistle = ttk.Combobox(options, state="readonly", width=30)
        self.whistle.pack(side="left", padx=(6, 18))
        self.whistle_ids: dict[str, str | None] = {}
        wheel_label = ttk.Label(options, text="Wheel radius (m)")
        wheel_label.pack(side="left")
        self.wheel = tk.StringVar()
        wheel_entry = ttk.Entry(options, textvariable=self.wheel, width=8)
        wheel_entry.pack(side="left", padx=(6, 0))
        wheel_help = ("Physical driving-wheel tyre radius in metres. Leave empty to review the measured candidates "
                      "in the pre-build dialog. This value is checked against powered wheels, not pilot or tender wheels.")
        Tooltip(wheel_label, wheel_help)
        Tooltip(wheel_entry, wheel_help)

        geometry = ttk.Frame(right)
        geometry.pack(side="top", fill="x", pady=(6, 0))
        ttk.Label(geometry, text="Reviewed geometry (optional)").pack(side="left")
        self.geometry = tk.StringVar()
        self.geometry_choices: dict[str, str] = {}  # label shown in the list -> review file
        entry = ttk.Combobox(geometry, textvariable=self.geometry, values=[])
        entry.pack(side="left", fill="x", expand=True, padx=6)
        self.geometry_box = entry
        def browse_geometry():
            path = filedialog.askopenfilename(parent=self.root, title="Choose reviewed geometry",
                                              initialdir=str(self._reports_folder()),
                                              filetypes=[("Geometry review", "*.json")])
            if path:
                self.geometry.set(path)
        ttk.Button(geometry, text="Browse…", command=browse_geometry).pack(side="left")
        Tooltip(entry, "A measured end-beam correction file for this locomotive. The list shows the reviews in your runs' "
                       "reports that fit this locomotive's current files, newest first; you can also type or browse to a "
                       "file. Leave empty unless its geometry has been reviewed. A review for different source files is refused.")

        ttk.Label(right, text="Checks", style="H2.TLabel").pack(side="top", anchor="w", pady=(10, 2))
        self.issues = ttk.Treeview(right, columns=("message",), show="tree", height=3, selectmode="none")
        self.issues.column("#0", width=28, stretch=False)
        self.issues.pack(side="top", fill="both", expand=True)
        for severity, (_, colour) in SEVERITY.items():
            self.issues.tag_configure(severity, foreground=COLOURS[colour])

        # bottom: progress of the current or last conversion
        progress = ttk.LabelFrame(root, text="Conversion", padding=10)
        progress.pack(side="bottom", fill="x", padx=12, pady=(6, 12), before=body)  # never squeezed by the panes
        stages = ttk.Frame(progress)
        stages.pack(side="left", fill="y")
        self.stage_rows = {}
        half = (len(STAGES) + 1) // 2
        for i, (name, description, _) in enumerate(STAGES):
            row, col = i % half, (i // half) * 2
            mark = tk.Label(stages, text="\u25cb", fg=COLOURS["muted"], width=2)
            mark.grid(row=row, column=col)
            label = ttk.Label(stages, text=STAGE_NAMES_SHORT.get(name, description))
            label.grid(row=row, column=col + 1, sticky="w", padx=(0, 12))
            self.stage_rows[name] = mark
        self.summary = ttk.Label(stages, text="", style="H2.TLabel", wraplength=520)
        self.summary.grid(row=half, column=0, columnspan=4, sticky="w", pady=(6, 0))
        side = ttk.Frame(progress)
        side.pack(side="left", fill="both", expand=True, padx=(16, 0))
        self.log = tk.Text(side, height=7, wrap="word", font=self.fonts["mono"], relief="flat", bg=COLOURS["panel"])
        self.log.pack(fill="both", expand=True)
        self.log.configure(state="disabled")
        buttons = ttk.Frame(side)
        buttons.pack(fill="x", pady=(6, 0))
        self.open_run = ttk.Button(buttons, text="Open run folder", state="disabled",
                                   command=lambda: self.last_run and open_path(self.last_run))
        self.open_run.pack(side="left")
        self.open_record = ttk.Button(buttons, text="Open draft record", state="disabled",
                                      command=lambda: self.last_run and open_path(self.last_run / "record" / "vehicle-record.json"))
        self.open_record.pack(side="left", padx=6)
        self.open_build = ttk.Button(buttons, text="Open build folder", state="disabled",
                                     command=lambda: self.last_run and open_path(self.last_output))
        self.open_build.pack(side="left")
        self.use_radius = ttk.Button(buttons, text="Use measured radius", state="disabled", command=self._use_candidate)
        self.use_radius.pack(side="left", padx=6)
        self.candidate: float | None = None
        self.use_geometry = ttk.Button(buttons, text="Use proposed geometry", state="disabled", command=self._use_proposal)
        self.use_geometry.pack(side="left")
        Tooltip(self.use_geometry, "After a stop on the end beam: the geometry review rr2dv measured from that build (its evidence "
                                   "is in the file). Fills in Reviewed geometry; press Convert to build with it.")
        self.proposal: Path | None = None

    # ---- plumbing -----------------------------------------------------------------------------------------------------
    def _modal_error(self, *args, **kwargs) -> None:
        """An error box blocks the window's event loop until it is closed: not a hang for the watchdog."""
        self._modal_box(messagebox.showerror, *args, **kwargs)

    def _modal_info(self, *args, **kwargs) -> None:
        """The same for the 'installed' box (a 32 s 'hang' dump was only the box waiting for its OK, 2026-10-01)."""
        self._modal_box(messagebox.showinfo, *args, **kwargs)

    def _modal_box(self, show, *args, **kwargs) -> None:
        self._modal = True
        try:
            show(*args, **kwargs)
        finally:
            self._modal = False
            self._beat = time.monotonic()

    def _watchdog(self) -> None:
        """Writes every thread's stack to the log folder when the window stops handling events for 30 s, so a hang
        leaves evidence instead of a frozen window and an empty log (2026-09-28)."""
        import faulthandler
        dumped = False
        while not self._closing:
            time.sleep(5)
            stalled = 0.0 if self._modal else time.monotonic() - self._beat
            if stalled > 30 and not dumped:
                path = applog.log_file().with_name(time.strftime("hang-%Y%m%d-%H%M%S.txt"))
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(f"derailroader window not responding for {stalled:.0f} s; stacks of every thread:\n")
                        f.flush()
                        faulthandler.dump_traceback(file=f, all_threads=True)
                    applog.get().error("window not responding for %.0f s; thread stacks written to %s", stalled, path)
                except OSError:
                    pass
                dumped = True
            elif stalled < 5:
                dumped = False

    def _pump(self) -> None:
        self._beat = time.monotonic()
        try:
            while True:
                try:
                    message = self.worker.inbox.get_nowait()
                except queue.Empty:
                    break
                try:
                    self._handle(*message)
                except Exception as e:  # a failing dialog must never stop the pump: that froze the window (2026-09-28)
                    self._dialog_failed(message[0], message[-1] if message[0] in ("review", "ask") else None, e)
        finally:
            self._pump_id = self.root.after(100, self._pump)

    def _handle(self, kind, *rest) -> None:
        if kind == "done":
            name, result, done = rest
            self.worker.busy = False
            if done:
                done(result)
        elif kind == "error":
            name, (error, trace), done = rest
            self.worker.busy = False
            self._log(f"{name} failed: {error}")
            self._set_busy(False)
            where = ""
            if name == "Conversion":
                self.summary.configure(text=f"Stopped: {error}", foreground=COLOURS["fail"])
                run = getattr(error, "rr2dv_run", None)  # the run that stopped, if it got that far (X39)
                if run:
                    self._show_run(run.path)
                    where = f"\n\nRun log: {run.path / 'run.log'}"
            self._modal_error(APP_NAME, f"{name} failed:\n\n{error}{where}\n\nApp log: {applog.log_file()}",
                                 parent=self.root)
        elif kind == "progress":
            stage, status, detail = rest
            self._stage(stage, status, detail)
        elif kind == "mods-progress":
            i, total = rest
            self.mods_status.configure(text=f"Reading locomotives… {i} of {total}")
        elif kind == "review":
            questions, answer = rest

            def open_review():
                from .reviewgui import show
                show(self.root, questions, answer)
            self._when_shown(kind, answer, open_review)
        elif kind == "ask":
            pack, sources, answer = rest
            self._when_shown(kind, answer, lambda: self._ask(pack, sources, answer))

    def _log(self, line: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", line + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_busy(self, busy: bool) -> None:
        self.root.configure(cursor="watch" if busy else "")
        self._update_convert_button(busy)

    # ---- installs and locomotives ------------------------------------------------------------------------------------------
    def refresh(self) -> None:
        self.c.reload()
        self.mods_status.configure(text="Finding your games…")
        self.worker.run("Finding games", self.c.installs, self._show_installs)

    def _show_installs(self, found) -> None:
        self.installs = found
        log = applog.get()
        log.info("games: Railroader %s; Derail Valley %s; CCL %s", found.railroader and found.railroader.root,
                 found.derail_valley and found.derail_valley.root, found.ccl)
        for key, why in found.problems.items():
            log.warning("%s: %s", key, why)
        missing = self.c.tools_missing()
        states = {"railroader": "ok" if found.railroader else "fail", "derail_valley": "ok" if found.derail_valley else "fail",
                  "ccl": "ok" if found.ccl else "fail", "tools": "warn" if missing else "ok"}
        tips = {"railroader": found.railroader and f"{found.railroader.root}",
                "derail_valley": found.derail_valley and f"{found.derail_valley.root}\nMods: {found.derail_valley.mods}",
                "ccl": "installed" if found.ccl else None,
                "tools": ("missing: " + ", ".join(missing)) if missing else "Unity, CarCreator, AssetRipper and Python are set"}
        for key, state in states.items():
            self.chips[key].configure(bg=COLOURS[state])
            self.chip_tips[key].text = tips[key] or found.problems.get(key, "not found")
        for key, why in found.problems.items():
            self._log(why)
        if missing:
            self._log("Set up in Settings: " + ", ".join(missing))
        if not found.railroader:
            self.mods_status.configure(text="Railroader was not found; set it in Settings.")
            return
        self.worker.run("Reading locomotives", lambda: self.c.list_locos(lambda i, n: self.worker.post(("mods-progress", i, n))),
                        self._show_mods)

    def _show_mods(self, mods) -> None:
        self.mods = mods
        applog.get().info("stock locomotives found: %d", len(mods))
        self._fill_mods()
        count = sum(len(m.locos) for m in mods)
        self.mods_status.configure(text=f"{count} stock steam locomotives")

    def _fill_mods(self) -> None:
        """Railroader's stock steam locomotives, one row each (name, identifier); the search box filters them."""
        self.tree.delete(*self.tree.get_children())
        needle = self.search.get().strip().casefold()
        rows = [(mod, i, n) for mod in self.mods for i, n in mod.locos if not needle or needle in f"{mod.label} {i} {n}".casefold()]
        if not rows:
            return
        node = self.tree.insert("", "end", iid="group::stock", text=f"Stock steam locomotives ({len(rows)})", open=True)
        for mod, ident, name in sorted(rows, key=lambda r: (r[2].casefold(), r[1])):
            self.tree.insert(node, "end", iid=f"loco::{mod.folder}::{ident}", text=f"{name}  ({ident})")

    def _on_select(self, _event=None) -> None:
        item = (self.tree.selection() or [""])[0]
        if not item.startswith("loco::"):
            return
        _, folder, ident = item.split("::", 2)
        if self.selected != (folder, ident):  # another loco's review would be refused
            self.geometry.set("")
            self._set_geometry_choices([])
        self.selected = (folder, ident)
        self.loco_title.configure(text=self.tree.item(item, "text").split("  (")[0])
        self.loco_sub.configure(text=f"{ident} in {Path(folder).name} — checking…")
        if self.report and self.report.get("_folder") == folder:
            self._show_loco()
        elif not self.worker.run("Checking the locomotive", lambda: {**self.c.scan(folder), "_folder": folder}, self._got_report):
            self.loco_sub.configure(text=f"{ident} in {Path(folder).name} — busy, select again when the current task ends")

    def _got_report(self, report) -> None:
        self.report = report
        self._show_loco()

    def _show_loco(self) -> None:
        folder, ident = self.selected
        inv = self.report["inventories"][ident]
        loco = next(l for l in self.report["steam_locomotives"] if l["id"] == ident)
        tender = inv.get("tender") or {}
        self.facts["tender"].configure(text=tender.get("id", "none (tank locomotive)"))
        self.facts["trucks"].configure(text=", ".join(t["id"] for t in inv["trucks"]) or "none")
        self.facts["parts"].configure(text=f"{len(inv['parts'])} part(s)" + (f", {len(inv['left_out'])} left out" if inv.get("left_out") else ""))
        purposes = sorted({c["purpose"] for c in inv["controls"]["radial"] if c.get("purpose")})
        self.facts["controls"].configure(text=f"{', '.join(purposes) or 'none'}; {len(inv['controls']['toggles'])} toggles")
        audio = inv["audio"]
        self.facts["sounds"].configure(text=f"vanilla {audio['basis'] or '(choose below)'} — {audio['rule']}")
        self.facts["sources"].configure(text=", ".join(s["id"] for s in inv.get("sources", [])) or "—")
        self.issues.delete(*self.issues.get_children())
        shown = [i for i in inv["issues"] if i["severity"] != "info"] or [{"severity": "info", "message": "No problems found."}]
        for issue in shown:
            mark, _ = SEVERITY[issue["severity"]]
            self.issues.insert("", "end", text=mark, values=(issue["message"],), tags=(issue["severity"],))
        self.livery.configure(values=loco.get("liveries") or ["(default)"])
        self.livery.current(0)
        whistle = inv.get("whistle") or {}
        default = f"(default: {whistle.get('id')}, from {whistle.get('source')})" if whistle.get("id") else "(none found)"
        self.whistle_ids = {default: None, **{f"{o['name']} ({o['id']})": o["id"] for o in whistle.get("options", [])}}
        self.whistle.configure(values=list(self.whistle_ids))
        self.whistle.current(0)
        self.loco_sub.configure(text=f"{ident} in {Path(folder).name}" + (" (Railroader base game)" if Path(folder).is_absolute() else ""))
        self._update_convert_button()
        self._find_geometry_reviews()

    def _reports_folder(self) -> Path:
        """Browse starts in the last run's reports (where its proposed review is), else in all the reports."""
        try:
            reports = self.c.reports()
        except Exception:
            return Path.home()
        last = reports / self.last_run.name if self.last_run else None
        return next((p for p in (last, reports, reports.parent) if p and p.is_dir()), Path.home())

    def _find_geometry_reviews(self) -> None:
        if not self.selected:
            return
        wanted = self.selected
        folder, ident = wanted

        def show(found):
            if self.selected == wanted:
                self._set_geometry_choices(found)
        self.worker.run("Finding geometry reviews", lambda: self.c.geometry_reviews(folder, ident), show)

    def _set_geometry_choices(self, found: list[dict]) -> None:
        self.geometry_choices = {r["label"]: r["path"] for r in found}
        self.geometry_box.configure(values=list(self.geometry_choices))
        if found:
            self._log(f"{len(found)} geometry review(s) fit this locomotive: choose one under Reviewed geometry if it needs one.")

    def _update_convert_button(self, busy: bool = False) -> None:
        reasons = []
        if busy or self.worker.busy:
            reasons.append("working…")
        if not self.selected or not self.report:
            reasons.append("choose a locomotive")
        elif self.selected and self.report and self.selected[1] in self.report["inventories"]:
            blockers = [i for i in self.report["inventories"][self.selected[1]]["issues"] if i["severity"] == "error"]
            if blockers:
                reasons.append(f"{len(blockers)} problem(s) must be fixed first")
        if getattr(self, "installs", None) and not self.installs.ready:
            reasons.append("a game or Custom Car Loader was not found")
        if self.c.tools_missing():
            reasons.append("tools missing (Settings)")
        self.convert_button.configure(state="disabled" if reasons else "normal")
        self.convert_hint.configure(text="; ".join(reasons) if reasons else "Ready.")

    # ---- converting -------------------------------------------------------------------------------------------------
    def convert(self) -> None:
        folder, ident = self.selected
        wheel = self.wheel.get().strip()
        try:
            wheel_radius = float(wheel) if wheel else None
            if wheel_radius is not None and not 0.1 <= wheel_radius <= 1.5:
                raise ValueError
        except ValueError:
            self._modal_error(APP_NAME, "The wheel radius must be a number of metres between 0.1 and 1.5.", parent=self.root)
            return
        audio = {1: "S060", 2: "S282"}.get(self.audio.current())
        chosen = self.geometry.get().strip()
        chosen = self.geometry_choices.get(chosen, chosen)
        geometry_review = Path(chosen) if chosen else None
        livery = self.livery.get() if self.livery.get() != "(default)" else None
        whistle = self.whistle_ids.get(self.whistle.get())
        for mark in self.stage_rows.values():
            mark.configure(text="\u25cb", fg=COLOURS["muted"])
        self.summary.configure(text="Converting\u2026", foreground="")
        self.last_run = None
        self.open_run.configure(state="disabled")
        self.open_record.configure(state="disabled")
        self.open_build.configure(state="disabled")
        self.use_radius.configure(state="disabled")
        self.use_geometry.configure(state="disabled")
        self._log(f"Converting {ident} from {folder}…")

        def progress(stage, status, detail):
            self.worker.post(("progress", stage, status, detail))

        def ask(pack, sources):  # on the worker thread: the notice itself opens on the Tk thread
            answer = {"event": threading.Event(), "value": False}
            self.worker.post(("ask", pack, sources, answer))
            answer["event"].wait()
            return answer["value"]

        def prebuild_review(questions):
            answer = {"event": threading.Event(), "value": None}
            self.worker.post(("review", questions, answer))
            answer['event'].wait()
            return answer['value']

        applog.get().info("converting %s from %s (livery %s, audio %s, wheel radius %s, whistle %s)", ident, folder, livery, audio, wheel_radius, whistle)
        started = self.worker.run("Conversion", lambda: self.c.convert(folder, ident, livery, audio, wheel_radius, progress, ask,
                                                                      geometry_review=geometry_review, prebuild_review=prebuild_review,
                                                                      whistle=whistle),
                                  self._converted)
        if started:
            self._set_busy(True)
        else:
            self.summary.configure(text="Still busy with another task: press Convert again in a moment.", foreground="")

    def _stage(self, stage, status, detail) -> None:
        if stage is None:
            return
        if stage not in self.stage_rows:
            self._log(f"{stage}: {detail}")
            return
        mark, colour = STAGE_MARKS.get(status, ("?", "muted"))
        self.stage_rows[stage].configure(text=mark, fg=COLOURS[colour])
        if detail and status != "not_available":  # the run's own closing message says it once
            self._log(f"{stage}: {detail}")

    def _show_run(self, path: Path) -> None:
        """The last run's folder, log and (if it got that far) draft record, whether it finished or stopped."""
        self._log(f"Full log: {path / 'run.log'}")
        self.last_run = path
        self.open_run.configure(state="normal")
        has_record = (path / "record" / "vehicle-record.json").is_file()
        self.open_record.configure(state="normal" if has_record else "disabled")
        from .jsonio import read_json
        data = read_json(path / 'run.json') if (path / 'run.json').is_file() else {}
        self.last_output = Path(data['output']) if data.get('output') else path / 'build'
        self.open_build.configure(state="normal" if self.last_output.is_dir() else "disabled")

    def _use_candidate(self) -> None:
        """Fills in the measured tread candidate the last run stopped on; the user still starts the conversion."""
        if self.candidate:
            self.wheel.set(f"{self.candidate:.4f}")
            self._log(f"Wheel radius set to the measured candidate {self.candidate:.4f} m; press Convert to build with it.")

    def _use_proposal(self) -> None:
        """Fills in the geometry review measured from the last run's end-beam survey; the user still starts the conversion."""
        if self.proposal:
            label = next((l for l, p in self.geometry_choices.items() if Path(p) == self.proposal), None)
            self.geometry.set(label or str(self.proposal))
            self._log(f"Reviewed geometry set to the proposal {self.proposal}; check its evidence, then press Convert.")

    def _converted(self, outcome) -> None:
        self._set_busy(False)
        applog.get().info("conversion finished (exit %s): %s; run %s", outcome.code, outcome.message,
                          outcome.run and outcome.run.path)
        if outcome.run:
            self._show_run(outcome.run.path)
        self._log(outcome.message)
        from .pipeline import EXIT_INCOMPLETE, EXIT_OK
        record = outcome.run.record if outcome.run else {}
        blocks = record.get("blocks") or []
        radius = next((b for b in blocks if b.get("code") == "needs-wheel-radius"), None)
        self.candidate = radius.get("candidate") if radius else None
        self.use_radius.configure(state="normal" if self.candidate else "disabled",
                                  text=f"Use measured radius ({self.candidate:.4f} m)" if self.candidate else "Use measured radius")
        proposal = record.get("geometryProposal")
        paths = [Path(proposal)] if proposal else []
        if proposal and outcome.run:
            paths.append(outcome.run.path / Path(proposal).name)
        self.proposal = next((p for p in paths if p.is_file()), None)
        self.use_geometry.configure(state="normal" if self.proposal else "disabled")
        self._find_geometry_reviews()
        installed = "Installed into your Derail Valley Mods folder. Check it in the game before calling it done: every control, " \
                    "closed throttle and whistle, brakes, lamps and the coupling (the conversion report lists what was chosen automatically)."
        if outcome.code == EXIT_OK:
            text, colour = installed, "ok"
        elif outcome.code == EXIT_INCOMPLETE and radius:
            text, colour = (f"Needs your answer: the wheel radius. Measured candidate {self.candidate:.4f} m; check it, then "
                            "'Use measured radius' (or type yours) and Convert again." if self.candidate else
                            "Needs your answer: the wheel radius (no candidate measured). Enter it and Convert again."), "warn"
        elif outcome.code == EXIT_INCOMPLETE and (record.get("stages", {}).get("publish") or {}).get("status") == "not_installed":
            text, colour = f"Built and audited, but not installed: {outcome.message.split(': ', 1)[-1]}", "warn"
        elif outcome.code == EXIT_INCOMPLETE:
            text, colour = f"Stopped before finishing: {outcome.message}", "warn"
        else:
            text, colour = f"Stopped: {outcome.message}", "fail"
        self.summary.configure(text=text, foreground=COLOURS[colour])
        if outcome.code == EXIT_OK:
            self._modal_info(APP_NAME, installed, parent=self.root)

    def _when_shown(self, kind: str, answer: dict, open_dialog, tries: int = 50) -> None:
        """A question needs the user: if the main window is minimised, restore it and wait until Windows has, then open
        the dialog. A dialog made on a minimised parent is hidden with it and its grab blocks the app (Trojan,
        2026-09-28). Nothing else is forced: forcing the dialog to the front (topmost) coincided with it never showing (L-27, 2026-09-28)."""
        if self.root.state() == "iconic" and tries > 0:
            self.root.deiconify()
            self.root.after(100, lambda: self._when_shown(kind, answer, open_dialog, tries - 1))
            return
        try:
            open_dialog()
        except Exception as e:
            self._dialog_failed(kind, answer, e)

    def _dialog_failed(self, kind: str, answer: dict | None, error: Exception) -> None:
        applog.get().error("window message %s failed:\n%s", kind, traceback.format_exc())
        self._log(f"{kind} failed: {error}")
        if answer is not None:  # the waiting conversion gets "cancelled" and stops cleanly instead of waiting forever
            answer["value"] = None if kind == "review" else False
            answer["event"].set()
        self._modal_error(APP_NAME, f"The {'vehicle choices' if kind == 'review' else kind} window could not open:\n\n"
                                       f"{error}\n\nThe details are in the app log: {applog.log_file()}", parent=self.root)

    def _ask(self, pack, sources, answer) -> None:
        top = tk.Toplevel(self.root)
        top.transient(self.root)

        def done(agreed: bool) -> None:
            answer["value"] = agreed
            top.grab_release()
            top.destroy()
            answer["event"].set()

        consent.build_notice(top, pack, sources, done)
        top.grab_set()

    # ---- settings ---------------------------------------------------------------------------------------------------
    def open_settings(self) -> None:
        SettingsDialog(self.root, self.c, on_saved=self.refresh)


class SettingsDialog:
    def __init__(self, parent: tk.Tk, controller: Controller, on_saved):
        self.c, self.on_saved = controller, on_saved
        self.top = top = tk.Toplevel(parent)
        top.title(f"{APP_NAME} settings")
        top.transient(parent)
        top.resizable(True, False)
        frame = ttk.Frame(top, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=f"Saved in {controller.settings_path}", style="Muted.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        values = controller.settings()
        self.vars = {}
        self.entries = []
        for row, (key, label, kind, _required) in enumerate(SETTINGS, start=1):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=2)
            var = tk.StringVar(value=str(values.get(key, "")))
            entry = ttk.Entry(frame, textvariable=var, width=60)
            entry.grid(row=row, column=1, sticky="we", padx=8, pady=2)
            self.entries.append(entry)
            ttk.Button(frame, text="Browse…", command=lambda v=var, k=kind: self._browse(v, k)).grid(row=row, column=2, pady=2)
            self.vars[key] = var
        frame.columnconfigure(1, weight=1)
        self.checks = tk.Text(frame, height=12, width=90, wrap="word", relief="flat", bg=COLOURS["panel"])
        self.checks.grid(row=len(SETTINGS) + 1, column=0, columnspan=3, sticky="we", pady=(12, 0))
        buttons = ttk.Frame(frame)
        buttons.grid(row=len(SETTINGS) + 2, column=0, columnspan=3, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="Open app log", command=lambda: applog.log_file().is_file() and open_path(applog.log_file())
                   ).pack(side="left", padx=4)
        self.check_button = ttk.Button(buttons, text="Check", command=self._check)
        self.check_button.pack(side="left", padx=4)
        self.save_button = ttk.Button(buttons, text="Save", command=self._save)
        self.save_button.pack(side="left", padx=4)
        ttk.Button(buttons, text="Close", command=top.destroy).pack(side="left", padx=4)
        self._check_results: queue.Queue = queue.Queue()
        self._checking = False
        top.update_idletasks()  # centre over the app, and keep focus here until closed
        x = parent.winfo_rootx() + (parent.winfo_width() - top.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - top.winfo_height()) // 3
        top.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        top.grab_set()

    def _browse(self, var: tk.StringVar, kind: str) -> None:
        path = filedialog.askopenfilename(parent=self.top) if kind == "file" else filedialog.askdirectory(parent=self.top)
        if path:
            var.set(path)

    def _save(self) -> None:
        self.c.save_settings({k: v.get() for k, v in self.vars.items()})
        self._check()
        self.on_saved()

    def _check(self) -> None:
        if self._checking:
            return
        self._checking = True
        self.check_button.state(["disabled"])
        self.save_button.state(["disabled"])
        for entry in self.entries:
            entry.state(["disabled"])
        self.checks.delete("1.0", "end")
        self.checks.insert("end", "Searching for tools and checking the paths shown above…\n")
        entered = {key: var.get() for key, var in self.vars.items()}

        def job():
            try:
                found = toolfinder.discover(self.c.machine, entered)
                checked = self.c.checks({**entered, **found})
                self._check_results.put((found, checked, None))
            except Exception as error:
                applog.get().exception("Settings check failed")
                self._check_results.put(({}, [], error))

        threading.Thread(target=job, daemon=True).start()
        self.top.after(100, self._poll_check)

    def _poll_check(self) -> None:
        if not self.top.winfo_exists():
            return
        try:
            found, checked, error = self._check_results.get_nowait()
        except queue.Empty:
            self.top.after(100, self._poll_check)
            return
        self._checking = False
        self.check_button.state(["!disabled"])
        self.save_button.state(["!disabled"])
        for entry in self.entries:
            entry.state(["!disabled"])
        self.checks.delete("1.0", "end")
        if error:
            self.checks.insert("end", f"Check failed: {error}\n")
            return
        for key, path in found.items():
            self.vars[key].set(path)
        if found:
            self.checks.insert("end", f"Found {len(found)} tool path(s). Click Save to keep them.\n\n")
        marks = {"ok": "✓", "warn": "!", "fail": "✗", "skip": "–"}
        for check in checked:
            self.checks.insert("end", f"{marks.get(check.status, '?')} {check.name}: {check.detail}\n")


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="rr2dv gui", description="The derailroader desktop app.")
    parser.add_argument("--machine", type=Path, help="settings file")
    parser.add_argument("--filter", default="", help="initial locomotive search text")
    args = parser.parse_args(argv)
    root = tk.Tk()
    app = App(root, Controller(args.machine))
    app.search.set(args.filter)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

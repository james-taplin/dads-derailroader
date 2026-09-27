"""The derailroader desktop app: pick a steam locomotive mod from the Railroader Mods folder, check it, convert it.

Tk/ttk from the standard library. Everything slow (finding installs, listing and scanning mods, converting) runs on a
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
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

from . import __version__, applog, consent
from .appmodel import SETTINGS, Controller
from .runs import STAGES

APP_NAME = "derailroader"
COLOURS = {"ok": "#2e7d32", "fail": "#c62828", "warn": "#b26a00", "idle": "#5f6b7a", "header": "#1f2933",
           "accent": "#a31515", "muted": "#6b7280", "panel": "#f4f5f7"}
STAGE_MARKS = {"pending": ("○", "muted"), "running": ("●", "warn"), "done": ("✓", "ok"), "failed": ("✗", "fail"),
               "not_available": ("–", "muted"), "incomplete": ("–", "muted")}
SEVERITY = {"error": ("✗", "fail"), "warning": ("!", "warn"), "info": ("i", "muted")}
STAGE_NAMES_SHORT = {"locate": "Find the locomotive", "link": "Resolve tender, trucks, parts", "stage": "Copy the inputs",
                     "extract": "Export bundles (AssetRipper)", "import": "Prepare the Unity project",
                     "probe": "Measure the model", "record": "Draft the vehicle record", "build": "Build the CCL pack",
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
        self.selected: tuple[str, str] | None = None  # (mod folder, loco id)
        self.last_run: Path | None = None
        self._build()
        self._pump_id = self.root.after(100, self._pump)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()

    def close(self) -> None:
        """Stop polling and close the window. A running conversion's worker thread is a daemon and ends with the app;
        its run folder records how far it got."""
        if self._pump_id:
            self.root.after_cancel(self._pump_id)
            self._pump_id = None
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

        # left: the mods
        left = ttk.Frame(body, padding=(0, 0, 8, 0), width=360)
        body.add(left, weight=1)
        ttk.Label(left, text="Locomotive mods", style="H2.TLabel").pack(anchor="w")
        ttk.Label(left, text="From your Railroader Mods folder", style="Muted.TLabel").pack(anchor="w")
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
        self.loco_sub = ttk.Label(titles, text="Pick a mod and a locomotive on the left.", style="Muted.TLabel")
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
        wheel_label = ttk.Label(options, text="Wheel radius (m)")
        wheel_label.pack(side="left")
        self.wheel = tk.StringVar()
        wheel_entry = ttk.Entry(options, textvariable=self.wheel, width=8)
        wheel_entry.pack(side="left", padx=(6, 0))
        wheel_help = ("Leave empty until you have reviewed the measured tread candidates in the draft record "
                      "(metadata.wheelCandidates); then enter the tread radius and convert again.")
        Tooltip(wheel_label, wheel_help)
        Tooltip(wheel_entry, wheel_help)

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

    # ---- plumbing -----------------------------------------------------------------------------------------------------
    def _pump(self) -> None:
        try:
            while True:
                kind, *rest = self.worker.inbox.get_nowait()
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
                    if name == "Conversion":
                        self.summary.configure(text=f"Stopped: {error}", foreground=COLOURS["fail"])
                    where = f"\n\nRun log: {self.last_run / 'run.log'}" if name == "Conversion" and self.last_run else ""
                    messagebox.showerror(APP_NAME, f"{name} failed:\n\n{error}{where}\n\nApp log: {applog.log_file()}",
                                         parent=self.root)
                elif kind == "progress":
                    stage, status, detail = rest
                    self._stage(stage, status, detail)
                elif kind == "mods-progress":
                    i, total = rest
                    self.mods_status.configure(text=f"Reading mods… {i} of {total}")
                elif kind == "ask":
                    pack, sources, answer = rest
                    self._ask(pack, sources, answer)
        except queue.Empty:
            pass
        self._pump_id = self.root.after(100, self._pump)

    def _log(self, line: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", line + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_busy(self, busy: bool) -> None:
        self.root.configure(cursor="watch" if busy else "")
        self._update_convert_button(busy)

    # ---- installs and mods ------------------------------------------------------------------------------------------
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
        tips = {"railroader": found.railroader and f"{found.railroader.root}\nMods: {found.railroader.mods}",
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
        self.worker.run("Reading mods", lambda: self.c.list_mods(lambda i, n: self.worker.post(("mods-progress", i, n))),
                        self._show_mods)

    def _show_mods(self, mods) -> None:
        self.mods = mods
        applog.get().info("mods: %d with steam locomotives", len(mods))
        self._fill_mods()
        count = sum(len(m.locos) for m in mods)
        self.mods_status.configure(text=f"{len(mods)} mods, {count} steam locomotives")

    def _fill_mods(self) -> None:
        self.tree.delete(*self.tree.get_children())
        needle = self.search.get().strip().casefold()
        for mod in self.mods:
            locos = [(i, n) for i, n in mod.locos if not needle or needle in f"{mod.folder} {i} {n}".casefold()]
            if not locos:
                continue
            node = self.tree.insert("", "end", iid=f"mod::{mod.folder}", text=mod.folder, open=bool(needle) or len(self.mods) < 8)
            for ident, name in locos:
                self.tree.insert(node, "end", iid=f"loco::{mod.folder}::{ident}", text=f"{name}  ({ident})")

    def _on_select(self, _event=None) -> None:
        item = (self.tree.selection() or [""])[0]
        if not item.startswith("loco::"):
            return
        _, folder, ident = item.split("::", 2)
        self.selected = (folder, ident)
        self.loco_title.configure(text=self.tree.item(item, "text").split("  (")[0])
        self.loco_sub.configure(text=f"{ident} in {folder} — checking…")
        if self.report and self.report.get("_folder") == folder:
            self._show_loco()
        elif not self.worker.run("Checking the mod", lambda: {**self.c.scan(folder), "_folder": folder}, self._got_report):
            self.loco_sub.configure(text=f"{ident} in {folder} — busy, select again when the current task ends")

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
        self.loco_sub.configure(text=f"{ident} in {folder}")
        self._update_convert_button()

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
            messagebox.showerror(APP_NAME, "The wheel radius must be a number of metres between 0.1 and 1.5.", parent=self.root)
            return
        audio = {1: "S060", 2: "S282"}.get(self.audio.current())
        livery = self.livery.get() if self.livery.get() != "(default)" else None
        for mark in self.stage_rows.values():
            mark.configure(text="\u25cb", fg=COLOURS["muted"])
        self.summary.configure(text="Converting\u2026", foreground="")
        self._log(f"Converting {ident} from {folder}…")

        def progress(stage, status, detail):
            self.worker.post(("progress", stage, status, detail))

        def ask(pack, sources):  # on the worker thread: the notice itself opens on the Tk thread
            answer = {"event": threading.Event(), "value": False}
            self.worker.post(("ask", pack, sources, answer))
            answer["event"].wait()
            return answer["value"]

        applog.get().info("converting %s from %s (livery %s, audio %s, wheel radius %s)", ident, folder, livery, audio, wheel_radius)
        started = self.worker.run("Conversion", lambda: self.c.convert(folder, ident, livery, audio, wheel_radius, progress, ask),
                                  self._converted)
        if started:
            self._set_busy(True)

    def _stage(self, stage, status, detail) -> None:
        if stage is None:
            return
        mark, colour = STAGE_MARKS.get(status, ("?", "muted"))
        self.stage_rows[stage].configure(text=mark, fg=COLOURS[colour])
        if detail and status != "not_available":  # the run's own closing message says it once
            self._log(f"{stage}: {detail}")

    def _converted(self, outcome) -> None:
        self._set_busy(False)
        applog.get().info("conversion finished (exit %s): %s; run %s", outcome.code, outcome.message,
                          outcome.run and outcome.run.path)
        if outcome.run:
            self._log(f"Full log: {outcome.run.path / 'run.log'}")
            self.last_run = outcome.run.path
            self.open_run.configure(state="normal")
            has_record = (outcome.run.path / "record" / "vehicle-record.json").is_file()
            self.open_record.configure(state="normal" if has_record else "disabled")
        self._log(outcome.message)
        from .pipeline import EXIT_INCOMPLETE, EXIT_OK
        if outcome.code == EXIT_OK:
            text, colour = "Installed into your Derail Valley Mods folder.", "ok"
        elif outcome.code == EXIT_INCOMPLETE:
            text, colour = "Draft record ready for review. Building the pack is not written yet.", "warn"
        else:
            text, colour = f"Stopped: {outcome.message}", "fail"
        self.summary.configure(text=text, foreground=COLOURS[colour])
        if outcome.code == 0:
            messagebox.showinfo(APP_NAME, "Installed into your Derail Valley Mods folder.", parent=self.root)

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
        for row, (key, label, kind, _required) in enumerate(SETTINGS, start=1):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=2)
            var = tk.StringVar(value=str(values.get(key, "")))
            ttk.Entry(frame, textvariable=var, width=60).grid(row=row, column=1, sticky="we", padx=8, pady=2)
            ttk.Button(frame, text="Browse…", command=lambda v=var, k=kind: self._browse(v, k)).grid(row=row, column=2, pady=2)
            self.vars[key] = var
        frame.columnconfigure(1, weight=1)
        self.checks = tk.Text(frame, height=12, width=90, wrap="word", relief="flat", bg=COLOURS["panel"])
        self.checks.grid(row=len(SETTINGS) + 1, column=0, columnspan=3, sticky="we", pady=(12, 0))
        buttons = ttk.Frame(frame)
        buttons.grid(row=len(SETTINGS) + 2, column=0, columnspan=3, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="Open app log", command=lambda: applog.log_file().is_file() and open_path(applog.log_file())
                   ).pack(side="left", padx=4)
        ttk.Button(buttons, text="Check", command=self._check).pack(side="left", padx=4)
        ttk.Button(buttons, text="Save", command=self._save).pack(side="left", padx=4)
        ttk.Button(buttons, text="Close", command=top.destroy).pack(side="left", padx=4)
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
        self.checks.delete("1.0", "end")
        marks = {"ok": "✓", "warn": "!", "fail": "✗", "skip": "–"}
        for check in self.c.checks():
            self.checks.insert("end", f"{marks.get(check.status, '?')} {check.name}: {check.detail}\n")


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="rr2dv gui", description="The derailroader desktop app.")
    parser.add_argument("--machine", type=Path, help="settings file")
    args = parser.parse_args(argv)
    root = tk.Tk()
    App(root, Controller(args.machine))
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

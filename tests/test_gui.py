"""The desktop app's window, driven for real. Needs Tk and a display (Windows; Linux under Xvfb); skipped otherwise."""
import json
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

from fixtures import loco, part, standard_mod, tool_machine, write_pack

try:
    import tkinter as tk
    _root = tk.Tk()
    _root.update_idletasks()  # drain ttk's pending ThemeChanged before destroying (board X40)
    _root.destroy()
    HAVE_TK = True
except Exception:  # no tkinter module, or no display
    HAVE_TK = False


@unittest.skipUnless(HAVE_TK, "needs tkinter and a display")
class Window(unittest.TestCase):
    def setUp(self):
        from rr2dv import gui
        from rr2dv.appmodel import Controller
        self.gui = gui
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.m = standard_mod(self.tmp)
        write_pack(self.m["search"] / "Another Loco Mod" / "a", objects=[loco("ls-460-a", parts=[part("Nope\\x", "y", "z")])],
                   assets={"ls-460-a": {"filename": "a.prefab"}})
        settings = self.tmp / "machine.json"
        settings.write_text(json.dumps({**tool_machine(self.tmp), "python": sys.executable}))
        self.root = tk.Tk()
        self.app = gui.App(self.root, Controller(settings))
        self.addCleanup(self.app.close)
        from rr2dv import reviewgui
        original_review = reviewgui.show
        def reviewed(parent, req, answer):
            value = None
            if self.app.wheel.get():
                value = {**{k:req[k] for k in ('schema','adapterVersion','vehicleId','fingerprint','catalogueHash')},
                    'values': {'trainBrake':'manual-lap','spawnMode':'radio-only','physics':'legacy-equivalent',
                               'steamHeat':'basis-approximation','wheelRadius':float(self.app.wheel.get()),
                               'cylinders':2,'spawnTracks':[],'acknowledgeExperimental':True}}
            answer['value'] = value
            answer['event'].set()
        reviewgui.show = reviewed
        self.addCleanup(setattr, reviewgui, 'show', original_review)

    def until(self, condition, timeout=60.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            self.root.update()
            if condition():
                return
            time.sleep(0.02)
        self.fail("timed out waiting for the window")

    def select(self, folder, ident):
        self.until(lambda: self.app.mods)
        self.app.tree.item(f"mod::{folder}", open=True)
        self.app.tree.selection_set(f"loco::{folder}::{ident}")
        self.until(lambda: self.app.report and self.app.report["_folder"] == folder and not self.app.worker.busy)
        self.root.update()

    def test_lists_mods_and_shows_a_ready_locomotive(self):
        self.until(lambda: self.app.mods)
        self.assertEqual(self.app.chips["railroader"].cget("bg"), self.gui.COLOURS["ok"])
        self.assertIn("2 mods, 2 steam locomotives", self.app.mods_status.cget("text"))
        self.select("Test Loco Mod", "ts-260-a")
        self.assertEqual(self.app.facts["tender"].cget("text"), "tt-260-a")
        self.assertEqual(str(self.app.convert_button.cget("state")), "normal")

    def test_geometry_box_lists_fitting_reviews_and_browse_starts_in_reports(self):
        from rr2dv import installs
        from rr2dv.pipeline import fingerprint, search_roots
        from rr2dv.rrmod import Index, inventory
        c = self.app.c
        rr = installs.railroader(c.machine)
        fp = fingerprint(inventory(Index(installs.mod_in_railroader(rr, "Test Loco Mod"), search_roots(rr, c.machine.search_roots())), "ts-260-a"))
        path = c.reports() / "20260929-192000-ts" / "geometry-review-proposed.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"schema": 1, "inputFingerprint": fp, "vehicles": {"ts-260-a": {"EndBeamProbeHeight": {
            "value": [1.0, 1.2], "unit": "m", "basis": "measured", "evidence": ["survey"]}}}}))
        self.select("Test Loco Mod", "ts-260-a")
        labels = list(self.app.geometry_box.cget("values"))
        self.assertEqual(len(labels), 1)
        self.assertEqual(self.app.geometry_choices[labels[0]], str(path))
        self.assertEqual(self.app.geometry.get(), "")  # listed, never chosen for the user
        self.assertEqual(self.app._reports_folder(), c.reports())

    def test_blocked_locomotive_cannot_be_converted(self):
        self.select("Another Loco Mod", "ls-460-a")
        self.assertEqual(str(self.app.convert_button.cget("state")), "disabled")
        self.assertIn("must be fixed", self.app.convert_hint.cget("text"))

    def test_search_filters_the_list(self):
        self.until(lambda: self.app.mods)
        self.app.search.set("460")
        self.root.update()
        self.assertEqual(self.app.tree.get_children(), ("mod::Another Loco Mod",))

    def test_settings_check_fills_found_path(self):
        candidate = self.tmp / "Unity 2019.4.40f1" / "Unity.exe"
        candidate.parent.mkdir()
        candidate.touch()
        dialog = self.gui.SettingsDialog(self.root, self.app.c, lambda: None)
        self.addCleanup(lambda: dialog.top.winfo_exists() and dialog.top.destroy())
        dialog.vars["unity"].set("")
        original = self.gui.toolfinder.discover
        self.gui.toolfinder.discover = lambda machine, entered: {"unity": str(candidate)}
        self.addCleanup(setattr, self.gui.toolfinder, "discover", original)
        dialog._check()
        self.until(lambda: not dialog._checking)
        self.assertEqual(dialog.vars["unity"].get(), str(candidate))
        self.assertIn("Unity Editor", dialog.checks.get("1.0", "end"))

    def test_a_failing_review_window_cancels_instead_of_freezing(self):
        from rr2dv import reviewgui
        from tkinter import messagebox
        def broken(parent, req, answer):
            raise ValueError("synthetic review failure")
        reviewgui.show = broken
        shown = []
        original = messagebox.showerror
        messagebox.showerror = lambda *a, **k: shown.append(a[1])
        self.addCleanup(setattr, messagebox, "showerror", original)
        self.select("Test Loco Mod", "ts-260-a")
        self.app.convert()
        self.until(lambda: not self.app.worker.busy and self.app.last_run, timeout=120)
        self.assertIn("synthetic review failure", shown[0])
        self.assertIn("Review cancelled", self.app.summary.cget("text"))
        self.assertIsNotNone(self.app._pump_id)  # the window keeps working

    def test_convert_shows_each_stage(self):
        self.select("Test Loco Mod", "ts-260-a")
        self.app.convert()
        self.until(lambda: not self.app.worker.busy and self.app.last_run, timeout=120)
        self.root.update()
        self.assertEqual(self.app.stage_rows["record"].cget("text"), "✓")
        self.assertEqual(self.app.stage_rows['review'].cget('text'), '?')
        self.assertIn('Review cancelled', self.app.summary.cget('text'))
        self.assertEqual(str(self.app.open_record.cget('state')), 'normal')
        self.assertFalse((self.app.last_run / 'build/vehicle-record.json').exists())

    def test_convert_with_the_radius_installs_after_the_notice(self):
        self.select("Test Loco Mod", "ts-260-a")
        self.app.wheel.set("0.5988")
        asked = []

        def fake_ask(pack, sources, answer):  # the real notice is tested on its own below
            asked.append(pack)
            answer["value"] = True
            answer["event"].set()
        self.app._ask = fake_ask
        shown = []
        original = self.gui.messagebox.showinfo
        self.gui.messagebox.showinfo = lambda title, message, **kw: shown.append(message)
        self.addCleanup(setattr, self.gui.messagebox, "showinfo", original)
        self.app.convert()
        self.until(lambda: not self.app.worker.busy and self.app.last_run and shown, timeout=120)
        self.root.update()
        self.assertEqual([self.app.stage_rows[s].cget("text") for s in ("build", "audit", "publish")], ["✓", "✓", "✓"])
        self.assertEqual(asked, ["Test ts-260-a"])
        self.assertIn("Installed into your Derail Valley Mods folder", self.app.summary.cget("text"))
        self.assertEqual(str(self.app.open_build.cget("state")), "normal")
        self.assertTrue((self.m["dv_mods"] / "Test ts-260-a" / "rr2dv.json").is_file())

    def test_stopped_conversion_keeps_its_run_folder(self):
        # X39: after a failure inside a run, Open run folder works and the error names run.log
        self.select("Test Loco Mod", "ts-260-a")
        self.app.convert()
        self.until(lambda: not self.app.worker.busy and self.app.last_run, timeout=120)
        for anim in (self.tmp / "work" / "_cache" / "assetripper").rglob("Drivers.anim"):
            anim.write_text("AnimationClip:\n  - path: path_0xdeadbeef_x\n")
        shown = []
        original = self.gui.messagebox.showerror
        self.gui.messagebox.showerror = lambda title, message, **kw: shown.append(message)
        self.addCleanup(setattr, self.gui.messagebox, "showerror", original)
        first = self.app.last_run
        self.app.convert()
        self.until(lambda: shown, timeout=120)
        self.assertNotEqual(self.app.last_run, first)
        self.assertEqual(str(self.app.open_run.cget("state")), "normal")
        self.assertEqual(str(self.app.open_record.cget("state")), "disabled")
        self.assertIn(f"Run log: {self.app.last_run / 'run.log'}", shown[0])
        self.assertEqual(self.app.stage_rows["import"].cget("text"), "\u2717")

    def test_notice_opens_inside_the_app_and_needs_ten_clicks(self):
        import threading
        answer = {"event": threading.Event(), "value": None}
        self.app._ask("INSERT_MOD_NAME", ["SOURCE_1"], answer)
        self.root.update()
        top = [w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)][-1]
        agree = next(b for b in top.winfo_children()[1].winfo_children() if b.cget("text") == "I agree")
        from rr2dv import consent
        for _ in range(consent.REQUIRED_CLICKS):
            agree.event_generate("<ButtonRelease-1>", x=5, y=5)
            self.root.update()
            time.sleep(consent.CLICK_GAP_S + 0.02)
        self.assertTrue(answer["event"].is_set())
        self.assertTrue(answer["value"])

    def test_settings_dialog_opens_with_the_saved_values(self):
        dialog = self.gui.SettingsDialog(self.root, self.app.c, on_saved=lambda: None)
        self.root.update()
        self.assertTrue(dialog.vars["unity"].get().endswith("Unity" + (".cmd" if sys.platform == "win32" else "")))
        dialog.top.destroy()


if __name__ == "__main__":
    unittest.main()

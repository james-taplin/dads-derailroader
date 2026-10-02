"""Entry point for the portable Windows app and its bundled helper scripts."""
from __future__ import annotations

import glob  # Imported dynamically by the bundled copy_deps.py helper.
import runpy
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--rr2dv-tool":
        from rr2dv.unityproject import tooling_root

        tools = (tooling_root() / "builder" / "tools").resolve()
        script = Path(sys.argv[2]).resolve()
        if not script.is_relative_to(tools):
            raise SystemExit("Helper script must be in the bundled tooling folder")
        sys.argv = [str(script), *sys.argv[3:]]
        runpy.run_path(str(script), run_name="__main__")
        return 0

    if len(sys.argv) > 1 and sys.argv[1] == "--rr2dv-self-test":
        import tkinter
        from rr2dv import __version__
        from rr2dv import catalogue, oiling, stock
        import tempfile
        from rr2dv.unityproject import tooling_root

        assert (tooling_root() / "builder" / "tools" / "resolve_clip_paths.py").is_file()
        assert (Path(__file__).resolve().parent / "rr2dv" / "unity" / "Rr2dvBuild.cs").is_file()
        tkinter.Tcl().eval("info patchlevel")
        # Exercise loose packaged catalogue data, including every engine/tender selection.
        with tempfile.TemporaryDirectory(prefix='rr2dv-self-test-') as tmp:
            for loco_id in stock.REAL_STEAM:
                record = {'vehicleId': loco_id, 'config': {'CarId': loco_id}}
                entry = stock.entry(loco_id)
                if not entry['tank']:
                    record['tender'] = {'config': {'CarId': entry['tender']['id']}}
                catalogue.prepare(Path(tmp), record)
                profile = oiling.library()['profiles'][loco_id]
                oil_record = {'vehicleId': loco_id, 'config': {'CarId': loco_id,
                    'WheelRadius': profile['wheelRadius'],
                    'EngineUnits': [{'DriverParts': ['driver']*len(profile['axleZ'])}]}}
                selection = oiling.prepare(oil_record, source_files={name:'0'*64 for name in stock.HASHED_FILES})
                assert selection['changedSourceFiles'] == list(stock.HASHED_FILES)
                assert len(selection['points']) >= max(6, 2*len(profile['axleZ']))
        print(f"Derailroader {__version__}: bundled tooling and Tk OK")
        return 0

    from rr2dv.gui import main as gui_main

    return gui_main()


if __name__ == "__main__":
    raise SystemExit(main())

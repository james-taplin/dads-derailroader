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
        from rr2dv import attribution, catalogue, oiling, review, reviewchoices, rrmod, stock
        import tempfile
        from rr2dv.unityproject import tooling_root

        assert (tooling_root() / "builder" / "tools" / "resolve_clip_paths.py").is_file()
        assert (Path(__file__).resolve().parent / "rr2dv" / "unity" / "Rr2dvBuild.cs").is_file()
        tkinter.Tcl().eval("info patchlevel")
        # Confirm the frozen app includes selected-content credits and ownership wording.
        unnamed = attribution.content('loco', 'Locomotive', 'locomotive model', 'loco', [])
        labels = attribution.source_labels([attribution.source([unnamed], ['loco'])])
        assert any('Giraffe Labs LLC' in label for label in labels)
        assert attribution.RIGHTS_NOTICE in labels
        assert len(stock.STEAM) == 10 and set(stock.STEAM) == stock.SUPPORTED_STEAM
        assert all(stock.refusal(loco_id) for loco_id in stock.EXCLUDED_STEAM)
        # Exercise the actual selection functions in the packaged executable.
        class WhistleIndex:
            def objects_of_kind(self, kind):
                return [(None, {'identifier': 'wh-6-reading', 'definition': {'kind': 'Whistle'}})]
        assert rrmod.whistle_options(WhistleIndex()) == []
        issues = []
        blocked = rrmod._whistle(WhistleIndex(), 'ls-440-a23',
            {'components': [{'kind': 'Whistle', 'defaultWhistleIdentifier': 'wh-6-reading'}]},
            None, {}, [], [], issues)
        assert not blocked['placed'] and issues[0].code == 'unsupported-whistle'
        # Exercise loose packaged catalogue data, including every engine/tender selection.
        with tempfile.TemporaryDirectory(prefix='rr2dv-self-test-') as tmp:
            for loco_id in stock.SUPPORTED_STEAM:
                record = {'vehicleId': loco_id, 'config': {'CarId': loco_id}}
                entry = stock.entry(loco_id)
                if not entry['tank']:
                    record['tender'] = {'config': {'CarId': entry['tender']['id']}}
                catalogue.prepare(Path(tmp), record)
                profile = oiling.library()['profiles'][loco_id]
                # Replay an incompatible saved radius through the frozen review path.
                source = {'mainDriverIndex': 0, 'wheelsets': [{'diameter': profile['wheelRadius']*2,
                          'animation': {'clipName': 'Drivers'}, 'numberOfAxles': len(profile['axleZ'])}]}
                questions = review.request({'vehicleId': loco_id, 'config': {'CarName': entry['displayName']},
                    'metadata': {}}, {loco_id: source}, {}, 'packaged-self-test')
                previous = review.resolve(questions, {**{k: questions[k] for k in reviewchoices.IDENTITY},
                    'values': {**questions['prefill']['values'], 'wheelRadius': profile['wheelRadius']+.0352723715782166,
                               'acknowledgeExperimental': True}})
                reviewchoices.remember(Path(tmp), previous)
                recovered = reviewchoices.prepare(questions, Path(tmp))
                assert recovered['prefill']['values']['wheelRadius'] == questions['prefill']['values']['wheelRadius']
                assert 'restored for review' in recovered['prefill']['origin']
                assert recovered['prefill']['values']['acknowledgeExperimental'] is False
                oil_record = {'vehicleId': loco_id, 'config': {'CarId': loco_id,
                    'WheelRadius': recovered['prefill']['values']['wheelRadius'],
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

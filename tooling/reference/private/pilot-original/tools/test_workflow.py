import tempfile
import subprocess
import sys
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch
import pilots


class WorkflowTests(unittest.TestCase):
    def test_nested_animation_files_are_repaired_without_flattening(self):
        with tempfile.TemporaryDirectory(dir=pilots.ROOT / 'analysis') as directory:
            root = Path(directory)
            source, dest = root / 'source', root / 'dest'
            source.mkdir()
            (source / 'body.prefab').write_text('''--- !u!1 &1
GameObject:
  m_Name: root
--- !u!4 &2
Transform:
  m_GameObject: {fileID: 1}
  m_Father: {fileID: 0}
--- !u!1 &3
GameObject:
  m_Name: wheel
--- !u!4 &4
Transform:
  m_GameObject: {fileID: 3}
  m_Father: {fileID: 2}
''')
            hashed = 'path_0x%X_test' % (zlib.crc32(b'wheel') & 0xffffffff)
            for folder in ('AnimationClip', 'tender'):
                (source / folder).mkdir()
                (source / folder / 'Brakes.anim').write_text(f'{folder}\npath: {hashed}\n')
            subprocess.run([sys.executable, str(pilots.ROOT / 'tools' / 'resolve_clip_paths.py'),
                str(source), str(root / 'report.txt'), '--apply', str(dest)], check=True, capture_output=True)
            for folder in ('AnimationClip', 'tender'):
                self.assertEqual((dest / folder / 'Brakes.anim').read_text(), f'{folder}\npath: wheel\n')
                self.assertIn(hashed, (source / folder / 'Brakes.anim').read_text())

    def test_output_cannot_escape_workspace(self):
        for path in [pilots.ROOT.parent / 'outside.json', pilots.ROOT / '..' / 'outside.json']:
            with self.assertRaises(ValueError):
                pilots.inside(path)

    def test_child_relative_hash_is_normalized_to_prefab_root(self):
        with tempfile.TemporaryDirectory(dir=pilots.ROOT / 'analysis') as directory:
            root = Path(directory)
            source, dest = root / 'source', root / 'dest'
            source.mkdir()
            blocks = []
            for go, tf, parent, name in [(1, 2, 0, 'root'), (3, 4, 2, 'Tender'), (5, 6, 4, 'Coal')]:
                blocks.append(f'--- !u!1 &{go}\nGameObject:\n  m_Name: {name}\n'
                    f'--- !u!4 &{tf}\nTransform:\n  m_GameObject: {{fileID: {go}}}\n  m_Father: {{fileID: {parent}}}\n')
            (source / 'body.prefab').write_text(''.join(blocks))
            hashed = 'path_0x%X_test' % (zlib.crc32(b'Coal') & 0xffffffff)
            (source / 'Coal.anim').write_text(f'path: {hashed}\n')
            subprocess.run([sys.executable, str(pilots.ROOT / 'tools' / 'resolve_clip_paths.py'),
                str(source), str(root / 'report.txt'), '--apply', str(dest)], check=True, capture_output=True)
            self.assertEqual((dest / 'Coal.anim').read_text(), 'path: Tender/Coal\n')

    def test_existing_project_is_preserved_before_any_manifest_write(self):
        before = (pilots.ROOT / 'config' / 'c21.json').read_bytes()
        with patch.object(pilots, 'manifest', side_effect=AssertionError('must not run')):
            with self.assertRaises(FileExistsError):
                pilots.prepare('c21')
        self.assertEqual(before, (pilots.ROOT / 'config' / 'c21.json').read_bytes())

    def test_duplicate_guid_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=pilots.ROOT / 'analysis') as directory:
            root = Path(directory)
            for name in ('one', 'two'):
                (root / (name + '.meta')).write_text('guid: abcdef0123456789\n')
            with self.assertRaisesRegex(ValueError, 'Duplicate GUID'):
                pilots.guid_index(root)

    def test_ambiguous_prefab_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=pilots.ROOT / 'analysis') as directory:
            root = Path(directory)
            for name in ('one', 'two'):
                (root / name).mkdir()
                (root / name / 'pilot.prefab').write_text('source')
            with self.assertRaisesRegex(ValueError, 'Expected one'):
                pilots.find_prefab(root, 'pilot.prefab')

    def test_tender_and_tank_resource_routes(self):
        c21 = pilots.read_json(pilots.ROOT / 'config' / 'c21-integration.json')['vehicles']
        s16 = pilots.read_json(pilots.ROOT / 'config' / 's16-integration.json')['vehicles']
        self.assertEqual(len(c21), 2)
        self.assertEqual(len(s16), 1)
        self.assertEqual(c21[0]['capacities'], {})
        self.assertAlmostEqual(c21[1]['capacities']['water']['dv_value'], 17034.353028)
        self.assertAlmostEqual(s16[0]['capacities']['water']['dv_value'], 3785.411784)
        self.assertEqual(sum(w['source']['numberOfAxles'] for w in c21[0]['wheelsets'] if w['role'] == 'powered'), 4)
        self.assertEqual(sum(w['source']['numberOfAxles'] for w in s16[0]['wheelsets'] if w['role'] == 'powered'), 3)


if __name__ == '__main__':
    unittest.main()

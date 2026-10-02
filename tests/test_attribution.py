"""Selected-content credits follow the review, whistle choice and installed pack."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from fixtures import standard_mod
from rr2dv import attribution, installs, publish, review, rrmod
from rr2dv.jsonio import read_json_lenient, sha256_file
from rr2dv.machine import Machine


class Credits(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.m = standard_mod(self.tmp)
        self.vehicle = self.m['mod'] / 'ts-260-a' / 'Definitions.json'
        from rr2dv import stock
        self.whistles = self.m['search'] / stock.WHISTLE_PACK / 'Definitions.json'

    def edit(self, path, change):
        data = read_json_lenient(path)
        change(data)
        path.write_text(json.dumps(data), encoding='utf-8')

    def inv(self, whistle=None):
        return rrmod.inventory(rrmod.Index(self.m['mod'], [self.m['search']]), 'ts-260-a',
                               hash_files=False, whistle=whistle)

    def named_whistles(self):
        def names(data):
            data['objects'][0]['metadata']['credits'] = 'Chris Currao'
            data['objects'][1]['metadata']['credits'] = 'Other Artist'
            # An unselected whistle sharing a mesh must not lend its author to it.
            other = copy.deepcopy(data['objects'][0])
            other['identifier'] = 'wh-unselected'
            other['metadata']['credits'] = 'Unselected Artist'
            data['objects'].append(other)
        self.edit(self.whistles, names)
        self.edit(self.whistles.with_name('Catalog.json'), lambda d:
                  d['assets']['TestChime'].update(credits='Mesh Artist'))

    def test_selected_definition_model_parts_and_trucks_only(self):
        self.named_whistles()
        def vehicle_names(data):
            data['objects'][0]['metadata']['credits'] = 'Elijah Gooden & Kyle Gabba'
            data['objects'][1]['metadata']['credits'] = 'Tender Artist'
            unrelated = copy.deepcopy(data['objects'][0])
            unrelated['identifier'] = 'unused'
            unrelated['definition']['modelIdentifier'] = 'unused'
            unrelated['metadata']['credits'] = 'Unused Loco Artist'
            data['objects'].append(unrelated)
        self.edit(self.vehicle, vehicle_names)
        self.edit(self.m['search'] / 'TruckMod/Trucks/Definitions.json', lambda d:
                  d['objects'][0].update(metadata={'credits': 'Elijah Gooen'}))
        self.edit(self.m['mod'] / 'parts/Catalog.json', lambda d:
                  d['assets']['bell'].update(metadata={'credits': 'Bell Artist'}))
        source = self.inv()['sources'][0]
        self.assertEqual(set(source['credits']), {'Elijah Gooden', 'Kyle Gabba', 'Tender Artist',
                         'Elijah Gooen', 'Bell Artist', 'Chris Currao', 'Mesh Artist'})
        whistle = next(c for c in source['contentCredits'] if c['role'] == 'whistle definition and mesh')
        self.assertEqual(whistle['credits'], ['Chris Currao', 'Mesh Artist'])
        self.assertNotIn('Unused Loco Artist', str(source))
        self.assertNotIn('Unselected Artist', str(source))

    def test_whistle_switch_changes_used_credits_and_options_without_mutation(self):
        self.named_whistles()
        inv = self.inv()
        before = copy.deepcopy(inv['sources'])
        option = next(o for o in inv['whistle']['options'] if o['id'] == 'wh-other')
        preview = attribution.preview_whistle(inv['sources'], option['contentCredit'])
        self.assertIn('Other Artist', preview[0]['credits'])
        self.assertNotIn('Chris Currao', preview[0]['credits'])
        self.assertEqual(inv['sources'], before)
        self.assertEqual(preview[0]['contentCredits'], self.inv('wh-other')['sources'][0]['contentCredits'])
        preview[0]['contentCredits'][-1]['credits'].append('Changed preview')
        self.assertEqual(option['contentCredit']['credits'], ['Other Artist'])

    def test_blank_and_asset_title_credits_use_publisher_and_preserve_raw_text(self):
        self.edit(self.vehicle, lambda d: d['objects'][0].update(metadata={'name': 'C-40 Mastodon', 'credits': 'Mastodon'}))
        source = self.inv()['sources'][0]
        loco = source['contentCredits'][0]
        self.assertEqual(loco['credits'], [])
        self.assertEqual(loco['creditText'], ['Mastodon'])
        self.assertEqual(loco['attribution'], 'Giraffe Labs LLC')
        self.assertIn('Giraffe Labs LLC', attribution.source_label(source))
        self.assertIn(attribution.RIGHTS_NOTICE, attribution.source_labels([source]))

    def test_preview_can_credit_valid_selection_when_default_is_missing(self):
        self.named_whistles()
        inv = self.inv('missing')
        selected = next(o for o in inv['whistle']['options'] if o['id'] == 'wh-test')['contentCredit']
        preview = attribution.preview_whistle(inv['sources'], selected)
        self.assertIn('Chris Currao', preview[0]['credits'])
        self.assertNotIn('Chris Currao', inv['sources'][0]['credits'])

    def test_disabled_and_missing_parts_and_whistles_are_not_credited(self):
        self.named_whistles()
        self.edit(self.m['mod'] / 'parts/Catalog.json', lambda d:
                  d['assets']['bell'].update(credits='Disabled Artist'))
        def disable(data):
            for c in data['objects'][0]['definition']['components']:
                if c['kind'] in ('PrefabModelComponent', 'Whistle'):
                    c['enabled'] = False
        self.edit(self.vehicle, disable)
        source = self.inv()['sources'][0]
        self.assertNotIn('Disabled Artist', source['credits'])
        self.assertNotIn('Chris Currao', source['credits'])
        self.assertNotIn('whistle definition and mesh', str(source))
        self.assertNotIn('whistle definition and mesh', str(self.inv('missing')['sources']))

    def test_separate_whistle_definition_and_model_packs_keep_both_credits(self):
        from fixtures import write_pack
        self.named_whistles()
        self.edit(self.whistles, lambda d: d['objects'][0]['definition']['model'].update(assetPackIdentifier='SeparateMesh'))
        write_pack(self.m['search'] / 'SeparateMesh', assets={
            'TestChime': {'filename': 'TestChime.prefab', 'credits': 'Separate Mesh Artist'}})
        inv = self.inv()
        self.assertIn('Chris Currao', inv['sources'][0]['credits'])
        self.assertIn('Separate Mesh Artist', inv['sources'][0]['credits'])
        self.assertNotIn('Mesh Artist', inv['sources'][0]['credits'])
        self.assertIn(self.whistles.parent.name, [p['name'] for p in inv['packs']])
        self.assertIn('SeparateMesh', [p['name'] for p in inv['packs']])

    def test_role_prefixes_aliases_and_supplied_spelling(self):
        self.assertEqual(attribution.artists('Models and textures: Elijah Gooden & Kyle Gabba'),
                         ['Elijah Gooden', 'Kyle Gabba'])
        self.assertEqual(attribution.artists('Ben Kinser (Xyvoracle); Elijah Gooen'),
                         ['Ben Kinser (Xyvoracle)', 'Elijah Gooen'])
        self.assertEqual(attribution.artists('Caboose', 'Caboose'), [])

    def test_review_copies_selected_source_credits(self):
        self.named_whistles()
        sources = self.inv()['sources']
        req = review.request({'vehicleId': 'x', 'config': {'CarName': 'Example'}, 'metadata': {'sources': sources}},
                             {'x': {}}, {}, 'fingerprint')
        self.assertEqual(req['sources'], sources)
        req['sources'][0]['credits'].append('Preview edit')
        self.assertNotIn('Preview edit', sources[0]['credits'])

    def test_install_notice_marker_and_provenance_include_same_selected_credits(self):
        self.named_whistles()
        sources = self.inv()['sources']
        dv = installs.derail_valley(Machine(None, self.m['games']))
        pack = self.tmp / 'build/RR2DV_TEST'
        pack.mkdir(parents=True)
        (pack / 'Info.json').write_text('{"Id":"RR2DV_TEST"}')
        labels = []
        def ask(name, credits):
            labels.extend(credits)
            return True
        dest, _ = publish.install(pack, dv, {'Info.json': sha256_file(pack / 'Info.json')}, sources, {}, ask)
        self.assertEqual(labels, attribution.source_labels(sources))
        for filename in (publish.NOTICE_FILE, publish.PROVENANCE_FILE):
            text = (dest / filename).read_text(encoding='utf-8')
            for phrase in ('Chris Currao', 'Mesh Artist', 'Giraffe Labs LLC', attribution.RIGHTS_NOTICE):
                self.assertIn(phrase, text)
            self.assertNotIn('Other Artist', text)
            self.assertNotIn('Unselected Artist', text)
        marker = json.loads((dest / publish.MARKER).read_text(encoding='utf-8'))
        self.assertEqual(marker['sources'], sources)


if __name__ == '__main__':
    unittest.main()

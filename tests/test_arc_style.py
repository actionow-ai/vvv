import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills' / 'vvv' / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from vvv_project import create_project, read_json, validate_catalog  # noqa: E402
import vvv_arc  # noqa: E402
import vvv_style  # noqa: E402


class ArcAndStyleTests(unittest.TestCase):
    """A small story template: an opening portrait pair, a chronological love story, a gallery and a close."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.kit = self.base / 'kit'
        (self.kit / 'catalog').mkdir(parents=True)
        (self.kit / 'src').mkdir()
        (self.kit / 'public' / 'music').mkdir(parents=True)
        (self.kit / 'src' / 'index.tsx').write_text('export const source = true;')
        (self.kit / 'package.json').write_text('{"private":true}')
        self.catalog = {
            'id': 'story', 'compositionId': 'VVV-Story',
            'defaultProps': {'copy': {'studio': 'Demo', 'title': 'Our story'}, 'fps': 30, 'music': {'src': '', 'volume': 1},
                             'photos': {}, 'stickers': True},
            'slots': {'groom': {'kind': 'single', 'count': 1, 'hint': 'groom solo portrait, portrait orientation'},
                      'bride': {'kind': 'single', 'count': 1, 'hint': 'bride solo portrait, portrait orientation'},
                      'love': {'kind': 'array', 'count': 3, 'min': 3},
                      'ending': {'kind': 'single', 'count': 1, 'hint': 'closing couple shot, landscape'},
                      'gallery': {'kind': 'array', 'count': 3, 'min': 1, 'max': 6, 'independent': True,
                                  'hint': 'wedding photos, grouped by set'}},
            'arc': [{'id': 'portraits', 'mood': ['romantic'],
                     'slots': [{'slot': 'groom', 'subject': ['groom']}, {'slot': 'bride', 'subject': ['bride']}]},
                    {'id': 'love-story', 'mood': ['sweet', 'funny'], 'order': 'chronological', 'slots': ['love']},
                    {'id': 'gallery', 'mood': ['romantic'], 'slots': ['gallery']},
                    {'id': 'ending', 'mood': ['moving'], 'slots': [{'slot': 'ending', 'subject': ['couple']}]}],
            'sample': {'from': 1, 'to': 3}, 'formats': {'16:9': {'width': 1920, 'height': 1080}}, 'defaultFormat': '16:9',
        }
        (self.kit / 'catalog' / 'story.json').write_text(json.dumps(self.catalog))
        self.photos = self.base / 'photos'
        self.photos.mkdir()
        # name: (size, tag) — input order deliberately mixed up
        self.shots = {
            'a-kitchen': ((90, 60), {'mood': ['funny'], 'subject': 'couple', 'when': '2023-02'}),
            'b-wedding1': ((60, 90), {'mood': ['romantic'], 'subject': 'couple', 'set': 'seaside'}),
            'c-bride': ((60, 90), {'mood': ['romantic'], 'subject': 'bride'}),
            'd-firstdate': ((90, 60), {'mood': ['sweet'], 'subject': 'couple', 'when': '2020-05'}),
            'e-vows': ((90, 60), {'mood': ['moving'], 'subject': 'couple'}),
            'f-groom': ((60, 90), {'mood': ['romantic'], 'subject': 'groom'}),
            'g-trip': ((90, 60), {'mood': ['sweet'], 'subject': 'couple', 'when': '2021-08'}),
            'h-wedding2': ((60, 90), {'mood': ['romantic'], 'subject': 'couple', 'set': 'seaside'}),
            'i-blurry': ((90, 60), {'skip': True}),
        }
        for index, (name, (size, _)) in enumerate(self.shots.items()):
            Image.new('RGB', size, (20 * index, 120, 200 - 20 * index)).save(self.photos / f'{name}.png')
        self.project = self.base / 'project'
        create_project(self.kit, 'story', [self.photos], self.project)
        items = read_json(self.project / 'assets.json')['items']
        self.ids = {Path(i['source']['name']).stem: i['id'] for i in items}

    def tag(self, **overrides):
        tags = {self.ids[name]: dict(tag, **overrides.get(name, {})) for name, (_, tag) in self.shots.items()}
        (self.project / 'creative' / 'photo-tags.json').write_text(json.dumps({'photos': tags}))

    def placed(self):
        photos = read_json(self.project / 'inputs.json')['props']['photos']
        names = {v: k for k, v in self.ids.items()}
        return {slot: names[v] if isinstance(v, str) else [names[x] for x in v] for slot, v in photos.items()}

    def test_photos_follow_the_arc_by_subject_mood_and_date(self):
        self.tag()
        result = vvv_arc.arrange(self.project)
        placed = self.placed()
        self.assertEqual((placed['groom'], placed['bride'], placed['ending']), ('f-groom', 'c-bride', 'e-vows'))
        self.assertEqual(placed['love'], ['d-firstdate', 'g-trip', 'a-kitchen'])  # by date, not input order
        self.assertEqual(placed['gallery'][:2], ['b-wedding1', 'h-wedding2'])
        self.assertNotIn('i-blurry', [p for v in placed.values() for p in (v if isinstance(v, list) else [v])])
        self.assertEqual([s['id'] for s in result['sections']], ['portraits', 'love-story', 'gallery', 'ending'])
        self.assertEqual(result['next']['action'], 'ask_user')
        self.assertTrue((self.project / 'creative' / 'arc-sheet.jpg').is_file())
        self.assertEqual(read_json(self.project / 'creative' / 'arc.json')['sections'][0]['slots'][0]['photos'][0]['match'], 'match')

    def test_pins_win_and_mismatches_are_reported(self):
        self.tag(**{'a-kitchen': {'slot': 'ending'}})
        result = vvv_arc.arrange(self.project)
        self.assertEqual(self.placed()['ending'], 'a-kitchen')
        self.assertFalse([d for d in result['diagnostics'] if d['code'] == 'ARC_MISMATCH' and 'ending' in d['location']])
        # Without a bride photo the bride slot falls back and says so.
        self.tag(**{'c-bride': {'skip': True}})
        result = vvv_arc.arrange(self.project)
        self.assertTrue(any(d['code'] == 'ARC_MISMATCH' and d['location'].endswith('bride') for d in result['diagnostics']))

    def test_bad_tags_fail_before_anything_changes(self):
        before = (self.project / 'inputs.json').read_bytes()
        for bad, code in [({'nope': {}}, 'TAGS_INVALID'), ({self.ids['c-bride']: {'mood': ['angry']}}, 'TAGS_INVALID'),
                          ({self.ids['c-bride']: {'slot': 'missing'}}, 'TAGS_INVALID')]:
            (self.project / 'creative' / 'photo-tags.json').write_text(json.dumps({'photos': bad}))
            with self.assertRaisesRegex(ValueError, code):
                vvv_arc.arrange(self.project)
        (self.project / 'creative' / 'photo-tags.json').unlink()
        with self.assertRaisesRegex(ValueError, 'TAGS_MISSING'):
            vvv_arc.arrange(self.project)
        self.assertEqual((self.project / 'inputs.json').read_bytes(), before)

    def test_the_arc_must_cover_every_slot_once(self):
        broken = dict(self.catalog, arc=self.catalog['arc'][:-1])
        with self.assertRaisesRegex(ValueError, 'missing: ending'):
            validate_catalog(broken, 'story')
        broken = dict(self.catalog, arc=[dict(self.catalog['arc'][0], mood=['angry'])] + self.catalog['arc'][1:])
        with self.assertRaisesRegex(ValueError, 'arc\\[0\\].mood'):
            validate_catalog(broken, 'story')

    def test_every_kit_template_has_a_valid_arc(self):
        kit = Path(__file__).resolve().parents[1] / 'kits' / 'remotion'
        for path in sorted((kit / 'catalog').glob('*.json')):
            catalog = validate_catalog(read_json(path), path.stem)
            if catalog.get('kind', 'template') == 'template':
                self.assertIn('arc', catalog, path.stem)

    def test_a_style_saved_from_one_film_applies_to_the_next(self):
        styles = self.base / 'styles'
        with patch.dict(os.environ, {'VVV_STYLES': str(styles)}):
            inputs = read_json(self.project / 'inputs.json')
            inputs['props']['copy']['studio'] = 'Harbor'
            inputs['props']['stickers'] = False
            track = self.project / 'public' / 'music' / 'our-song.mp3'
            track.parent.mkdir(parents=True, exist_ok=True)
            track.write_bytes(b'fake mp3')
            (track.parent / 'our-song.beats.json').write_text('{"beats": [0.5, 1.0]}')
            inputs['props']['music'] = {'src': 'music/our-song.mp3', 'volume': 0.7}
            (self.project / 'inputs.json').write_text(json.dumps(inputs))
            manifest = read_json(self.project / 'vvv.json')
            manifest['workflow']['approvedConstraints'] = ['Names in Chinese, then English.']
            (self.project / 'vvv.json').write_text(json.dumps(manifest))

            saved = vvv_style.save(self.project, 'harbor', keep=['copy.studio'], constraints=['Faces in the first 3 s.'])
            self.assertEqual((saved['props'], saved['constraints'], saved['music']), (['copy.studio', 'stickers'], 2, 'music/our-song.mp3'))
            self.assertTrue((styles / 'harbor' / 'music' / 'our-song.beats.json').is_file())
            with self.assertRaisesRegex(ValueError, 'DESTINATION_EXISTS'):
                vvv_style.save(self.project, 'harbor')

            second = self.base / 'second'
            create_project(self.kit, 'story', [self.photos], second)
            applied = vvv_style.apply(second, 'harbor')
            props = read_json(second / 'inputs.json')['props']
            self.assertEqual((props['copy']['studio'], props['copy']['title'], props['stickers']), ('Harbor', 'Our story', False))
            self.assertEqual((props['music']['src'], props['music']['volume']), ('music/our-song.mp3', 0.7))
            self.assertEqual((second / 'public' / 'music' / 'our-song.mp3').read_bytes(), b'fake mp3')
            workflow = read_json(second / 'vvv.json')['workflow']
            self.assertEqual(workflow['approvedConstraints'], ['Names in Chinese, then English.', 'Faces in the first 3 s.'])
            self.assertEqual((workflow['style']['name'], applied['constraintsAdded']), ('harbor', 2))
            self.assertEqual(vvv_style.apply(second, 'harbor')['constraintsAdded'], 0)  # applying twice adds nothing

    def test_a_style_that_does_not_fit_changes_nothing(self):
        styles = self.base / 'styles'
        (styles / 'broken').mkdir(parents=True)
        (styles / 'broken' / 'style.json').write_text(json.dumps({
            'vvvStyle': '1', 'name': 'broken', 'constraints': ['x'],
            'templates': {'story': {'props': {'photos': {'groom': 'photo-missing'}}}}}))
        before = {p: (self.project / p).read_bytes() for p in ('inputs.json', 'vvv.json')}
        with patch.dict(os.environ, {'VVV_STYLES': str(styles)}):
            with self.assertRaisesRegex(ValueError, 'STYLE_INVALID'):
                vvv_style.apply(self.project, 'broken')
            with self.assertRaisesRegex(ValueError, 'STYLE_NOT_FOUND'):
                vvv_style.apply(self.project, 'nowhere')
        self.assertEqual({p: (self.project / p).read_bytes() for p in before}, before)
        self.assertFalse((self.project / 'creative' / 'style.json').exists())

    def test_a_style_steers_the_arc_and_init_applies_it(self):
        styles = self.base / 'styles'
        (styles / 'warm').mkdir(parents=True)
        (styles / 'warm' / 'style.json').write_text(json.dumps({
            'vvvStyle': '1', 'name': 'warm', 'arc': {'ending': {'mood': ['funny']}}}))
        env = {**os.environ, 'VVV_STYLES': str(styles)}
        output = self.base / 'styled'
        result = subprocess.run([sys.executable, str(SCRIPTS / 'vvv.py'), 'init', '--kit', str(self.kit), '--template', 'story',
                                 '--photos', str(self.photos), '--style', 'warm', '--output', str(output)],
                                capture_output=True, text=True, env=env)
        self.assertEqual(json.loads(result.stdout)['style']['style'], 'warm', result.stdout)
        self.project, self.ids = output, {Path(i['source']['name']).stem: i['id'] for i in read_json(output / 'assets.json')['items']}
        self.tag()
        vvv_arc.arrange(output)
        self.assertEqual(self.placed()['ending'], 'a-kitchen')  # the preset asked for a funny close
        failed = subprocess.run([sys.executable, str(SCRIPTS / 'vvv.py'), 'init', '--kit', str(self.kit), '--template', 'story',
                                 '--photos', str(self.photos), '--style', 'nowhere', '--output', str(self.base / 'never')],
                                capture_output=True, text=True, env=env)
        self.assertEqual(json.loads(failed.stdout)['code'], 'STYLE_NOT_FOUND')
        self.assertFalse((self.base / 'never').exists())


if __name__ == '__main__':
    unittest.main()

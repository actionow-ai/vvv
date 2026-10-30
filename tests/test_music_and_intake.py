"""Offline tests for music add/fit, photo downscaling, outfit groups and describe timing."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills' / 'vvv' / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from vvv_project import create_project, describe_template, read_json, write_json  # noqa: E402
import vvv_arc  # noqa: E402
import vvv_music  # noqa: E402

PAGES = [('open', 8), ('pair', 16), ('peak', 8), ('end', 8)]


def beat_map(count=200, period=0.5, chorus=64):
    """A steady song whose energy jumps at `chorus` and stays high."""
    beats = [round(0.2 + i * period, 3) for i in range(count)]
    energy = [0.3 if i < chorus else 0.8 for i in range(count)]
    return {'bpm': 120, 'duration': beats[-1] + 2, 'beats': beats, 'downbeats': beats[::4], 'energy': energy}


class MusicFitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'project'
        (self.project / 'public' / 'music').mkdir(parents=True)
        (self.project / 'catalog').mkdir()
        (self.project / 'scripts').mkdir()
        write_json(self.project / 'catalog' / 'demo.json', {
            'id': 'demo', 'timeline': {'pages': [{'id': i, 'beats': b} for i, b in PAGES], 'climax': 'peak',
                                       'pace': {'prop': 'pace', 'min': 1, 'max': 2}}})
        write_json(self.project / 'inputs.json', {'template': 'demo', 'props': {
            'music': {'src': 'music/song.mp3', 'volume': 1, 'trimBeforeSec': 0, 'fadeInSec': 0.3, 'fadeOutSec': 3}, 'pace': 1}})
        write_json(self.project / 'public' / 'music' / 'song.beats.json', beat_map())

    def test_chorus_is_the_rise_into_the_first_sustained_high(self):
        self.assertEqual(vvv_music.chorus_beat(beat_map(chorus=64)), 64)

    def test_fit_lands_the_climax_page_on_the_chorus_with_watchable_holds(self):
        result = vvv_music.fit(self.project)
        self.assertGreaterEqual(result['shortestHold'], 5.0)
        peak = next(p for p in result['pages'] if p['page'] == 'peak')
        # the climax page starts on song beat 64 (32.2 s) once the trim is taken off
        self.assertAlmostEqual(peak['from'] + result['trimBeforeSec'], 32.2, delta=0.06)
        self.assertNotIn('chorusOffsetBeats', result)
        self.assertEqual(read_json(self.project / 'inputs.json')['props']['pace'], 1)  # not applied

    def test_fit_apply_writes_the_trim_and_pace(self):
        result = vvv_music.fit(self.project, seconds=30, apply=True)
        props = read_json(self.project / 'inputs.json')['props']
        self.assertEqual((props['pace'], props['music']['trimBeforeSec']), (result['pace'], result['trimBeforeSec']))
        self.assertGreaterEqual(props['music']['fadeInSec'], 0.8)

    def test_a_template_without_a_timeline_is_reported(self):
        write_json(self.project / 'catalog' / 'demo.json', {'id': 'demo'})
        with self.assertRaisesRegex(ValueError, 'TIMELINE_UNKNOWN'):
            vvv_music.fit(self.project)

    def test_add_copies_measures_records_and_uses_the_track(self):
        song = Path(self.temp.name) / '咱们结婚吧.mp3'
        song.write_bytes(b'ID3' + bytes(100))
        (self.project / 'scripts' / 'analyze-music.mjs').write_text('// stand-in')

        def analyzer(command, **kwargs):
            Path(command[3]).write_text(json.dumps(beat_map()))
            return subprocess.CompletedProcess(command, 0, '', '')
        with patch('shutil.which', return_value='/usr/bin/node'), patch('subprocess.run', side_effect=analyzer):
            result = vvv_music.add(self.project, song)
        self.assertEqual(result['src'], 'music/咱们结婚吧.mp3')
        track = read_json(self.project / 'public' / 'music' / 'sources.json')['tracks'][-1]
        self.assertEqual((track['distribution'], track['bpm']), ('owner', 120))
        self.assertEqual(read_json(self.project / 'inputs.json')['props']['music']['src'], 'music/咱们结婚吧.mp3')


class IntakeTests(unittest.TestCase):
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
        catalog = {'id': 'pairs', 'compositionId': 'VVV-Pairs', 'defaultProps': {'fps': 30, 'photos': {}, 'copy': {}, 'music': {'src': '', 'volume': 1}},
                   'slots': {'cover': {'kind': 'single', 'count': 1},
                             'pair': {'kind': 'array', 'count': 4, 'groups': [2, 2], 'hint': 'two spreads, one outfit each'}},
                   'arc': [{'id': 'all', 'mood': ['romantic'], 'slots': ['cover', 'pair']}],
                   'sample': {'from': 0, 'to': 1}, 'formats': {'16:9': {'width': 1920, 'height': 1080}}, 'defaultFormat': '16:9'}
        (self.kit / 'catalog' / 'pairs.json').write_text(json.dumps(catalog))
        self.photos = self.base / 'photos'
        self.photos.mkdir()

    def test_init_downscales_large_photos_and_records_it(self):
        Image.new('RGB', (3000, 4500), (200, 180, 160)).save(self.photos / 'big.jpg')
        for n in range(4):
            Image.new('RGB', (60, 90), (n * 40, 90, 120)).save(self.photos / f's{n}.jpg')
        project = self.base / 'project'
        create_project(self.kit, 'pairs', [self.photos], project)
        items = {Path(i['source']['name']).stem: i for i in read_json(project / 'assets.json')['items']}
        self.assertEqual((items['big']['width'], items['big']['height']), (1707, 2560))
        self.assertIn('downscale-2560', items['big']['processing'])
        with Image.open(project / 'public' / items['big']['file']) as image:
            self.assertEqual(image.size, (1707, 2560))
        self.assertNotIn('downscale-2560', items['s0']['processing'])

    def test_faces_without_opencv_is_a_warning_not_a_failure(self):
        for n in range(5):
            Image.new('RGB', (60, 90), (n * 40, 90, 120)).save(self.photos / f's{n}.jpg')
        with patch.dict(sys.modules, {'cv2': None}):
            result = create_project(self.kit, 'pairs', [self.photos], self.base / 'project', faces=True)
        self.assertIn('FACES_UNAVAILABLE', [d['code'] for d in result['diagnostics']])

    def test_each_group_of_a_slot_keeps_one_outfit_and_the_next_changes_it(self):
        sets = ['red', 'white', 'red', 'white', 'red']
        for n, outfit in enumerate(sets):
            Image.new('RGB', (60, 90), (n * 40, 90, 120)).save(self.photos / f'{n}-{outfit}.jpg')
        project = self.base / 'project'
        create_project(self.kit, 'pairs', [self.photos], project)
        ids = {Path(i['source']['name']).stem: i['id'] for i in read_json(project / 'assets.json')['items']}
        tags = {pid: {'mood': ['romantic'], 'subject': 'couple', 'set': name.split('-')[1]} for name, pid in ids.items()}
        (project / 'creative' / 'photo-tags.json').write_text(json.dumps({'photos': tags}))
        vvv_arc.arrange(project)
        pair = read_json(project / 'inputs.json')['props']['photos']['pair']
        outfit = {pid: name.split('-')[1] for name, pid in ids.items()}
        first, second = [outfit[p] for p in pair[:2]], [outfit[p] for p in pair[2:]]
        self.assertEqual(len(set(first)), 1)
        self.assertEqual(len(set(second)), 1)
        self.assertNotEqual(first[0], second[0])


class UpdateTests(unittest.TestCase):
    def test_update_takes_kit_changes_keeps_local_edits_and_adds_new_files(self):
        base = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, base)
        kit = base / 'kit'
        (kit / 'catalog').mkdir(parents=True)
        (kit / 'src' / 'templates').mkdir(parents=True)
        (kit / 'public' / 'music').mkdir(parents=True)
        (kit / 'package.json').write_text('{"private":true}')
        (kit / 'src' / 'index.tsx').write_text('export const a = 1;')
        (kit / 'src' / 'templates' / 'scene.tsx').write_text('export const b = 1;')
        catalog = {'id': 'one', 'compositionId': 'VVV-One', 'defaultProps': {'fps': 30, 'photos': {}, 'copy': {},
                   'music': {'src': '', 'volume': 1}}, 'slots': {}, 'sample': {'from': 0, 'to': 1},
                   'formats': {'16:9': {'width': 1920, 'height': 1080}}, 'defaultFormat': '16:9'}
        (kit / 'catalog' / 'one.json').write_text(json.dumps(catalog))
        project = base / 'project'
        create_project(kit, 'one', [], project)
        self.assertTrue((project / 'kit-files.json').is_file())
        (kit / 'src' / 'index.tsx').write_text('export const a = 2;')            # kit change, untouched locally
        (kit / 'src' / 'templates' / 'scene.tsx').write_text('export const b = 2;')
        (project / 'src' / 'templates' / 'scene.tsx').write_text('export const b = 9;')  # edited locally too
        (kit / 'src' / 'templates' / 'new.tsx').write_text('export const c = 1;')
        from vvv_project import update_project
        report = update_project(project, kit)
        self.assertEqual((report['updated'], report['added'], report['conflicts']),
                         (['src/index.tsx'], ['src/templates/new.tsx'], ['src/templates/scene.tsx']))
        self.assertEqual((project / 'src' / 'index.tsx').read_text(), 'export const a = 1;')  # dry run
        update_project(project, kit, apply=True)
        self.assertEqual((project / 'src' / 'index.tsx').read_text(), 'export const a = 2;')
        self.assertEqual((project / 'src' / 'templates' / 'scene.tsx').read_text(), 'export const b = 9;')
        self.assertTrue((project / 'src' / 'templates' / 'new.tsx').is_file())
        self.assertEqual(update_project(project, kit)['conflicts'], ['src/templates/scene.tsx'])


class DescribeTimingTests(unittest.TestCase):
    def test_describe_reports_shown_fields_and_seconds_per_page(self):
        kit = Path(__file__).resolve().parents[1] / 'kits' / 'remotion'
        result = describe_template(kit, 'editorial')
        self.assertIn('date', result['shows']['couple'])
        self.assertEqual(result['timeline']['climax'], 'heart')
        self.assertGreater(result['timing']['filmSeconds'], 60)
        self.assertEqual(len(result['timing']['pages']), len(result['timeline']['pages']))


if __name__ == '__main__':
    unittest.main()

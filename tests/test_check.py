"""Behavior of the rendered-video checks; real FFmpeg integration skips if not configured."""
import array
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave

from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills' / 'vvv' / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from vvv_check import beat_sync, check_file, check_project, check_video, still_runs, visual_peaks  # noqa: E402
from vvv_media import run_tool  # noqa: E402


class MeasurementTests(unittest.TestCase):
    def test_still_runs_report_only_holds_at_or_above_the_limit(self):
        # Frame-to-frame (lag 1) at 10 fps: motion, 2 s still, motion, 0.9 s still.
        changes = [5.0] * 5 + [0.0] * 20 + [5.0] * 3 + [0.1] * 9
        runs = still_runs(changes, 10, 1.0)
        self.assertEqual(runs, [{'from': 0.5, 'to': 2.5, 'seconds': 2.0}])
        self.assertEqual(still_runs(changes, 10, 0.5)[1]['seconds'], 0.9)

    def test_lagged_drift_extends_runs_back_to_the_first_still_frame(self):
        # drift[k] compares frame k+5 with frame k: frames 20..44 identical gives zeros at k = 20..39.
        drift = [3.0] * 20 + [0.0] * 20 + [3.0] * 10
        self.assertEqual(still_runs(drift, 10, 1.0, lag=5), [{'from': 2.0, 'to': 4.4, 'seconds': 2.4}])

    def test_slow_push_is_motion_across_half_a_second_but_not_frame_to_frame(self):
        from vvv_check import frame_changes
        # A gradient sliding one gray level per frame: each frame barely differs from the last.
        frames = [bytes(x + i for x in range(0, 200, 4)) for i in range(30)]
        self.assertTrue(all(c < 1.1 for c in frame_changes(frames)))
        self.assertTrue(all(c >= 5 for c in frame_changes(frames, lag=15)))

    def test_peaks_find_isolated_cuts_and_ignore_the_edges(self):
        changes = [0.2] * 100
        for index in (4, 30, 60, 98):
            changes[index] = 40.0
        times = [round(p['t'], 2) for p in visual_peaks(changes, 10)]
        self.assertEqual(times, [3.1, 6.1])

    def test_beat_sync_measures_distance_to_the_nearest_shifted_beat(self):
        peaks = [{'t': 1.0, 's': 10}, {'t': 2.05, 's': 9}]
        on_beat = beat_sync(peaks, [11.0, 12.0, 13.0], offset=10.0)
        self.assertEqual(on_beat['meanMs'], 25)
        self.assertEqual(on_beat['within66ms'], 1.0)
        self.assertEqual(on_beat['worst'], [])
        self.assertIsNone(beat_sync([], [1.0], 0))

    def test_beat_sync_lists_the_worst_peaks_signed(self):
        peaks = [{'t': 1.0, 's': 10}, {'t': 1.78, 's': 9}, {'t': 3.2, 's': 8}]
        result = beat_sync(peaks, [1.0, 2.0, 3.0], offset=0)
        self.assertEqual([(w['t'], w['beat'], w['offsetMs']) for w in result['worst']], [(1.78, 1, -220), (3.2, 2, 200)])


def write_project(project, catalog, props):
    """A minimal project that passes validate_project: check_project validates before measuring."""
    (project / 'catalog').mkdir(parents=True, exist_ok=True)
    (project / 'public' / 'music').mkdir(parents=True, exist_ok=True)
    (project / 'catalog' / f"{catalog['id']}.json").write_text(json.dumps(catalog))
    (project / 'vvv.json').write_text(json.dumps({'vvvFormat': '1.0', 'kind': 'project', 'template': {'id': catalog['id']}}))
    (project / 'assets.json').write_text(json.dumps({'version': '0.1', 'items': []}))
    (project / 'inputs.json').write_text(json.dumps({'template': catalog['id'], 'props': {'fps': 30, **props}}))
    src = props.get('music', {}).get('src')
    if src:
        (project / 'public' / src).write_bytes(b'audio')


class ProjectCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'project'
        self.catalog = {'id': 'reel', 'compositionId': 'VVV-Reel', 'defaultProps': {}, 'slots': {},
                        'sample': {'from': 0, 'to': 6}, 'formats': {'16:9': {'width': 1920, 'height': 1080}},
                        'defaultFormat': '16:9', 'music': {'required': True}, 'check': {'maxStillSeconds': 3}}

    def test_an_invalid_project_is_reported_before_any_measurement(self):
        write_project(self.project, self.catalog, {'format': '16:9', 'music': {'src': 'music/a.ogg'}})
        for props in [{'format': 'wide', 'music': {'src': 'music/a.ogg'}}, {'music': {'src': '../outside.ogg'}},
                      {'music': []}, {'format': 7}]:
            with self.subTest(props=props):
                (self.project / 'inputs.json').write_text(json.dumps({'template': 'reel', 'props': {'fps': 30, **props}}))
                result = check_project(self.project, video=self.project / 'missing.mp4', ffmpeg='/missing', ffprobe='/missing')
                self.assertEqual((result['status'], result['code']), ('failed', 'PROJECT_INVALID'))
                self.assertEqual(result['validation']['status'], 'failed')
        (self.project / 'inputs.json').write_text('[]')
        self.assertEqual(check_project(self.project)['code'], 'PROJECT_INVALID')

    def test_a_malformed_beat_map_is_a_clear_error(self):
        write_project(self.project, self.catalog, {'format': '16:9', 'music': {'src': 'music/a.ogg'}})
        (self.project / 'video.mp4').write_bytes(b'not decoded before the beat map is read')
        for content in ['{"beats": "x"}', '{"beats": [1, true]}', '7']:
            with self.subTest(content=content):
                (self.project / 'public' / 'music' / 'a.beats.json').write_text(content)
                with self.assertRaisesRegex(ValueError, 'BEATS_INVALID'):
                    check_project(self.project, video=self.project / 'video.mp4', ffmpeg='/missing', ffprobe='/missing')


class CheckIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ffmpeg = os.environ.get('VVV_TEST_FFMPEG') or shutil.which('ffmpeg')
        cls.ffprobe = os.environ.get('VVV_TEST_FFPROBE') or shutil.which('ffprobe')
        if not cls.ffmpeg or not cls.ffprobe:
            raise unittest.SkipTest('Check integration requires FFmpeg/ffprobe on PATH or '
                                    'VVV_TEST_FFMPEG and VVV_TEST_FFPROBE.')
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        base = Path(cls.temp.name)
        frames = base / 'frames'
        frames.mkdir()
        # 6 s at 10 fps, 96×54: a cut every 0.5 s for 2 s, a 2.5 s hold, then cuts again.
        colors = ['#d23c3c', '#2f55d4', '#2fa65a', '#e0b030']
        for index in range(60):
            t = index / 10
            if 2.0 <= t < 4.5:
                color = '#808080'
            else:
                color = colors[int(t / 0.5) % len(colors)]
            Image.new('RGB', (96, 54), color).save(frames / ('%03d.png' % index))
        tone = base / 'tone.wav'
        values = array.array('h', (int(8000 * math.sin(2 * math.pi * 440 * n / 8000)) for n in range(48000)))
        if sys.byteorder != 'little':
            values.byteswap()
        with wave.open(str(tone), 'wb') as output:
            output.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
            output.writeframes(values.tobytes())
        cls.silent = base / 'silent.mp4'
        cls.sound = base / 'sound.mp4'
        run_tool([cls.ffmpeg, '-v', 'error', '-nostdin', '-framerate', '10', '-i', str(frames / '%03d.png'),
                  '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-an', str(cls.silent)])
        run_tool([cls.ffmpeg, '-v', 'error', '-nostdin', '-i', str(cls.silent), '-i', str(tone),
                  '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'aac', str(cls.sound)])

    def codes(self, result):
        return {c['code']: c['status'] for c in result['checks']}

    def test_hold_longer_than_limit_fails_and_shorter_limit_passes(self):
        strict = check_video(self.sound, self.ffmpeg, self.ffprobe, expected=(1920, 1080), max_still=2.0)
        self.assertEqual(strict['status'], 'failed')
        still = next(c for c in strict['checks'] if c['code'] == 'STILL')
        self.assertEqual(len(still['runs']), 1)
        self.assertAlmostEqual(still['runs'][0]['from'], 2.0, delta=0.15)
        self.assertAlmostEqual(still['runs'][0]['seconds'], 2.4, delta=0.15)
        relaxed = check_video(self.sound, self.ffmpeg, self.ffprobe, expected=(1920, 1080), max_still=3.0)
        self.assertEqual(self.codes(relaxed), {'FORMAT': 'passed', 'RESOLUTION': 'warning',
                                               'AUDIO': 'passed', 'STILL': 'passed'})
        self.assertEqual(relaxed['status'], 'passed')

    def test_missing_audio_fails_only_when_music_is_required(self):
        optional = check_video(self.silent, self.ffmpeg, self.ffprobe, max_still=3.0)
        self.assertEqual(self.codes(optional)['AUDIO'], 'warning')
        required = check_video(self.silent, self.ffmpeg, self.ffprobe, max_still=3.0, music_required=True)
        self.assertEqual(self.codes(required)['AUDIO'], 'failed')
        self.assertEqual(self.codes(required)['BEAT_SYNC'], 'warning')

    def test_wrong_aspect_fails_format(self):
        result = check_video(self.sound, self.ffmpeg, self.ffprobe, expected=(1080, 1920), max_still=3.0)
        self.assertEqual(self.codes(result)['FORMAT'], 'failed')

    def test_cuts_on_beats_pass_sync_and_off_beat_grid_fails(self):
        on_grid = [0.5 * k for k in range(13)]
        good = check_video(self.sound, self.ffmpeg, self.ffprobe, max_still=3.0, beats=on_grid)
        self.assertEqual(self.codes(good)['BEAT_SYNC'], 'passed')
        shifted = check_video(self.sound, self.ffmpeg, self.ffprobe, max_still=3.0, beats=on_grid, beat_offset=-0.25)
        self.assertEqual(self.codes(shifted)['BEAT_SYNC'], 'failed')

    def test_project_check_uses_catalog_format_limits_and_sample_offset(self):
        project = Path(self.temp.name) / 'project'
        write_project(project, {
            'id': 'reel', 'compositionId': 'VVV-Reel', 'defaultProps': {}, 'slots': {},
            'sample': {'from': 0, 'to': 6}, 'formats': {'16:9': {'width': 1920, 'height': 1080}},
            'defaultFormat': '16:9', 'music': {'required': True}, 'check': {'maxStillSeconds': 3}},
            {'format': '16:9', 'music': {'src': 'music/track.ogg', 'trimBeforeSec': 1.0}})
        (project / 'out').mkdir()
        shutil.copyfile(self.sound, project / 'out' / 'sample.mp4')
        # Beats are music time: video time 0 is music time 1.0 (trim) + 10.0 (sample start).
        (project / 'public' / 'music' / 'track.beats.json').write_text(json.dumps(
            {'beats': [11.0 + 0.5 * k for k in range(13)]}))
        (project / 'out' / 'sample.report.json').write_text(json.dumps({
            'mode': 'sample', 'output': 'out/sample.mp4', 'createdAt': '2026-10-14T00:00:00Z',
            'sourceTimeRange': {'from': 10.0, 'to': 16.0}}))
        result = check_project(project, ffmpeg=self.ffmpeg, ffprobe=self.ffprobe)
        self.assertEqual(self.codes(result)['BEAT_SYNC'], 'passed')
        self.assertEqual(result['source']['report'], 'out/sample.mp4')
        self.assertEqual(result['status'], 'passed')

    def test_later_soundtrack_tracks_are_chained_into_film_time(self):
        project = Path(self.temp.name) / 'two-tracks'
        catalog = {'id': 'reel', 'compositionId': 'VVV-Reel', 'defaultProps': {}, 'slots': {},
                   'sample': {'from': 0, 'to': 6}, 'formats': {'16:9': {'width': 1920, 'height': 1080}},
                   'defaultFormat': '16:9', 'music': {'required': True},
                   'check': {'maxStillSeconds': 3, 'tracks': [{'src': 'music/b.ogg', 'at': 4.0, 'from': 4.4}]}}
        write_project(project, catalog, {'format': '16:9', 'music': {'src': 'music/a.ogg'}})
        # Track A has beats only for the first two seconds; track B (file second 0 at film 4.0) has the rest.
        (project / 'public' / 'music' / 'a.beats.json').write_text(json.dumps({'beats': [0.5 * k for k in range(5)]}))
        (project / 'public' / 'music' / 'b.beats.json').write_text(json.dumps({'beats': [0.5 + 0.5 * k for k in range(6)]}))
        alone = check_project(project, video=self.sound, ffmpeg=self.ffmpeg, ffprobe=self.ffprobe)
        self.assertEqual(self.codes(alone)['BEAT_SYNC'], 'passed')
        catalog['check']['tracks'] = []
        (project / 'catalog' / 'reel.json').write_text(json.dumps(catalog))
        first_only = check_project(project, video=self.sound, ffmpeg=self.ffmpeg, ffprobe=self.ffprobe)
        self.assertEqual(self.codes(first_only)['BEAT_SYNC'], 'failed')


    def test_any_file_such_as_a_reference_is_measured_against_its_own_beat_map(self):
        beats = Path(self.temp.name) / 'reference.beats.json'
        beats.write_text(json.dumps({'beats': [0.5 * k for k in range(13)]}))
        result = check_file(self.sound, beats, max_still=2.0, ffmpeg=self.ffmpeg, ffprobe=self.ffprobe)
        codes = self.codes(result)
        self.assertNotIn('FORMAT', codes)
        self.assertEqual(codes['BEAT_SYNC'], 'passed')
        self.assertEqual(codes['STILL'], 'failed')
        self.assertEqual(result['source']['beats'], str(beats))
        cli = subprocess.run([sys.executable, str(SCRIPTS / 'vvv.py'), 'check', '--video', str(self.sound),
                              '--beats', str(beats), '--ffmpeg', self.ffmpeg, '--ffprobe', self.ffprobe],
                             capture_output=True, text=True)
        self.assertEqual(cli.returncode, 0, cli.stdout + cli.stderr)
        self.assertEqual(json.loads(cli.stdout)['status'], 'passed')
        missing = subprocess.run([sys.executable, str(SCRIPTS / 'vvv.py'), 'check'], capture_output=True, text=True)
        self.assertEqual(missing.returncode, 1)
        self.assertEqual(json.loads(missing.stdout)['code'], 'CHECK_TARGET')


if __name__ == '__main__':
    unittest.main()

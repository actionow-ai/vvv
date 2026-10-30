"""Offline tests for the musicdl route: a stand-in musicdl module, no network and no install."""

from contextlib import contextmanager, redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills' / 'vvv' / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import vvv_song as song  # noqa: E402

AUDIO = b'ID3' + bytes(range(256)) * 4


class Song:
    def __init__(self, source, identifier, name, work_dir):
        self.source, self.identifier, self.song_name = source, identifier, name
        self.singers, self.album, self.duration, self.file_size, self.ext = '齐晨', '咱们结婚吧', '00:03:48', '3.5MB', 'mp3'
        self.work_dir = work_dir

    @property
    def save_path(self):
        return os.path.join(self.work_dir, f'{self.song_name} - {self.identifier}.{self.ext}')


def fake_musicdl(produce=True, created=None):
    """A module shaped like `from musicdl import musicdl` with a MusicClient that records its setup."""
    class MusicClient:
        def __init__(self, music_sources, init_music_clients_cfg):
            self.sources, self.config = music_sources, init_music_clients_cfg
            if created is not None:
                created.append(self)

        def search(self, keyword):
            print('progress bar noise')
            return {s: [Song(s, f'{s[:2]}{n}', f'{keyword}', self.config[s]['work_dir']) for n in (1, 2)] for s in self.sources}

        def download(self, song_infos):
            if produce:
                for info in song_infos:
                    Path(info.save_path).write_bytes(AUDIO)
            return song_infos

    package = types.ModuleType('musicdl')
    package.__version__ = '9.9.9'
    package.musicdl = types.SimpleNamespace(MusicClient=MusicClient)
    return package


class SongTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'project'
        (self.project / 'public' / 'music').mkdir(parents=True)
        (self.project / 'inputs.json').write_text('{"template": "editorial", "props": {}}')
        # Never hand over to a real musicdl environment on the test machine.
        venv = patch.object(song, 'VENV_PYTHON', str(Path(self.temp.name) / 'no-python'))
        venv.start()
        self.addCleanup(venv.stop)
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop('VVV_MUSICDL_PYTHON', None)

    @contextmanager
    def installed(self, module):
        with patch.dict(sys.modules, {'musicdl': module}):
            yield

    def call(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = song.main(list(argv))
        return code, json.loads(out.getvalue())

    def test_missing_musicdl_asks_the_user_to_install_it_and_never_installs(self):
        with patch.dict(sys.modules, {'musicdl': None}), patch('subprocess.run') as runner:
            code, result = self.call('doctor')
            code2, result2 = self.call('search', '--keyword', '咱们结婚吧')
        self.assertEqual((code, result['musicdl'], result['next']['action']), (0, 'missing', 'ask_user'))
        self.assertIn('pip install musicdl', result['next']['say'])
        self.assertEqual((code2, result2['code']), (1, 'MUSICDL_MISSING'))
        runner.assert_not_called()

    def test_search_lists_recordings_and_passes_no_cookies(self):
        created = []
        with self.installed(fake_musicdl(created=created)):
            code, result = self.call('search', '--keyword', '咱们结婚吧', '--source', 'NeteaseMusicClient')
        self.assertEqual(code, 0)
        self.assertEqual([r['id'] for r in result['results']], ['Ne1', 'Ne2'])
        config = created[0].config['NeteaseMusicClient']
        self.assertFalse(any('cookie' in key for key in config))

    def test_add_requires_the_personal_use_confirmation(self):
        with self.installed(fake_musicdl()):
            code, result = self.call('add', '--project', str(self.project), '--keyword', 'x', '--source', 'QQMusicClient', '--id', 'QQ1')
        self.assertEqual((code, result['code']), (1, 'PERSONAL_USE_REQUIRED'))

    def test_add_saves_a_personal_track_and_records_it(self):
        with self.installed(fake_musicdl()):
            code, result = self.call('add', '--project', str(self.project), '--keyword', '咱们结婚吧', '--source', 'QQMusicClient',
                                     '--id', 'QQ2', '--personal-use')
        self.assertEqual(code, 0, result)
        target = self.project / result['file']
        self.assertTrue(target.name.startswith('personal-') and target.read_bytes() == AUDIO)
        track = json.loads((self.project / 'public' / 'music' / 'sources.json').read_text())['tracks'][-1]
        self.assertEqual((track['distribution'], track['file']), ('personal', target.name))
        self.assertIn('Never redistribute', track['license'])
        self.assertEqual(result['next']['command'][:3], ['npm', 'run', 'beats'])

    def test_an_unknown_id_or_an_empty_download_writes_nothing(self):
        with self.installed(fake_musicdl()):
            code, result = self.call('add', '--project', str(self.project), '--keyword', 'x', '--source', 'QQMusicClient',
                                     '--id', 'nope', '--personal-use')
        self.assertEqual((code, result['code']), (1, 'NOT_FOUND'))
        with self.installed(fake_musicdl(produce=False)):
            code, result = self.call('add', '--project', str(self.project), '--keyword', 'x', '--source', 'QQMusicClient',
                                     '--id', 'QQ1', '--personal-use')
        self.assertEqual((code, result['code']), (1, 'DOWNLOAD_FAILED'))
        self.assertEqual(list((self.project / 'public' / 'music').iterdir()), [])

    def test_personal_songs_are_refused_by_packaging(self):
        rules = json.loads((Path(__file__).resolve().parents[1] / 'kits' / 'remotion' / 'package-licenses.json').read_text())['rules']
        sys.path.insert(0, str(SCRIPTS))
        import vvv_package as package  # noqa: PLC0415
        rule = package.license_for('public/music/personal-咱们结婚吧.mp3', rules, 'project')
        self.assertIs(rule['redistribute'], False)


if __name__ == '__main__':
    unittest.main()

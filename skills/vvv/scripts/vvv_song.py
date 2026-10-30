#!/usr/bin/env python3
"""A song the user names, fetched with their own musicdl install for their own film (personal use only).

  doctor                                         is musicdl installed? (it is never installed for the user)
  search --keyword WORDS [--source CLIENT ...]   candidate recordings with their source and id
  add --project P --keyword WORDS --source CLIENT --id ID --personal-use [--name NAME]
                                                 download that recording into public/music/personal-*.

musicdl (https://github.com/CharlesPikachu/musicdl) is licensed for noncommercial use only, and the
songs it reaches belong to their rights holders. VVV calls it only when the user has installed it and
asked for a specific song for their own film; it passes no login cookies, so nothing paid is reached.
Downloaded songs are recorded as personal, stay out of templates, and make `pack` refuse the project.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

from vvv import ask_user, emit, fix, run

VENV_PYTHON = '~/.vvv/musicdl/bin/python'
DEFAULT_SOURCES = ('NeteaseMusicClient', 'QQMusicClient', 'KuwoMusicClient', 'MiguMusicClient', 'KugouMusicClient')
AUDIO = {'.mp3', '.flac', '.m4a', '.ogg', '.wav', '.aac'}
LICENSE = ('Personal use in the owner\'s own film only; rights stay with the rights holders. '
           'Fetched with the user\'s musicdl install (noncommercial license). Never redistribute or package.')
INSTALL = ask_user('要按歌名下载歌曲，需要你自己安装开源工具 musicdl（仅限非商业、个人使用；歌曲版权归原权利人）：'
                   '在终端运行 pip install musicdl 后告诉我。我不会替你安装。')


class SongError(Exception):
    def __init__(self, code, message, step=None):
        super().__init__(message)
        self.code, self.message, self.step = code, message, step


def load_musicdl():
    try:
        from musicdl import musicdl  # noqa: PLC0415 - optional, user-installed
    except ImportError:
        # musicdl needs a newer Python than some systems ship; a user may keep it in its own environment.
        python = Path(os.environ.get('VVV_MUSICDL_PYTHON') or VENV_PYTHON).expanduser()
        if python.is_file() and Path(sys.executable).resolve() != python.resolve() and not os.environ.get('VVV_SONG_REEXEC'):
            os.environ['VVV_SONG_REEXEC'] = '1'
            os.execv(str(python), [str(python), str(Path(__file__).resolve()), *sys.argv[1:]])
        raise SongError('MUSICDL_MISSING', 'musicdl is not installed; VVV does not install it.', INSTALL) from None
    return musicdl


def client(sources, work_dir, limit):
    musicdl = load_musicdl()
    # No cookies are passed: only what a source serves without a login is reachable.
    config = {s: {'work_dir': str(work_dir), 'search_size_per_source': limit} for s in sources}
    with redirect_stdout(sys.stderr):
        return musicdl.MusicClient(music_sources=list(sources), init_music_clients_cfg=config)


def find(sources, keyword, work_dir, limit):
    engine = client(sources, work_dir, limit)
    with redirect_stdout(sys.stderr):
        results = engine.search(keyword=keyword)
    return engine, [song for songs in results.values() for song in (songs or [])]


def summary(song):
    item = {'source': song.source, 'id': str(song.identifier), 'name': song.song_name, 'singers': song.singers,
            'album': song.album, 'duration': song.duration, 'size': song.file_size, 'ext': song.ext}
    return {k: v for k, v in item.items() if v not in (None, '', 'NULL')}


def search(args):
    with tempfile.TemporaryDirectory(prefix='vvv-song-') as work:
        _, songs = find(args.source or DEFAULT_SOURCES, args.keyword, work, args.limit)
        return {'status': 'passed', 'results': [summary(s) for s in songs],
                'note': 'Ask the user which recording to use; download only the one they name.'}


def slug(text):
    value = re.sub(r'[^\w]+', '-', str(text), flags=re.UNICODE).strip('-').lower()
    return value[:60] or 'song'


def add(args):
    if not args.personal_use:
        raise SongError('PERSONAL_USE_REQUIRED', 'Pass --personal-use once the user has asked for this song for their own film.',
                        fix('Confirm with the user that the song is for their own, noncommercial film, then add --personal-use.'))
    root = Path(args.project).expanduser().resolve()
    if not (root / 'public').is_dir() or not (root / 'inputs.json').is_file():
        raise SongError('INVALID_PROJECT', 'Use an initialized VVV project (public/ and inputs.json).')
    folder = root / 'public' / 'music'
    for path in (root / 'public', folder, folder / 'sources.json'):
        if path.is_symlink():
            raise SongError('UNSAFE_PATH', f'{path.relative_to(root)} is a symbolic link.')
    with tempfile.TemporaryDirectory(prefix='vvv-song-') as work:
        engine, songs = find([args.source], args.keyword, work, 10)
        song = next((s for s in songs if str(s.identifier) == args.id), None)
        if song is None:
            raise SongError('NOT_FOUND', f'{args.source} returned no recording with id {args.id} for that keyword.',
                            fix('Search again and use a source and id from the results.'))
        with redirect_stdout(sys.stderr):
            done = engine.download([song])
        saved = [Path(s.save_path) for s in (done or []) if getattr(s, 'save_path', None)]
        saved = [p for p in saved if p.is_file() and p.stat().st_size > 0]
        if not saved:
            raise SongError('DOWNLOAD_FAILED', 'musicdl did not produce a file for that recording (it may need a paid account).',
                            fix('Pick another recording, or ask the user for the song as a file.'))
        source_file = saved[0]
        suffix = source_file.suffix.lower()
        if suffix not in AUDIO:
            raise SongError('DOWNLOAD_FAILED', f'musicdl produced a {suffix or "typeless"} file, not audio.')
        name = f"personal-{slug(args.name or song.song_name)}{suffix}"
        target = folder / name
        if target.exists():
            raise SongError('FILE_EXISTS', f'public/music/{name} already exists.', fix('Pass another --name.'))
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_file, target)
    data = target.read_bytes()
    record = {'file': name, 'title': song.song_name, 'author': song.singers or '',
              'source': f'musicdl {args.source} id {args.id}', 'license': LICENSE, 'distribution': 'personal',
              'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    sources_path = folder / 'sources.json'
    sources = json.loads(sources_path.read_text(encoding='utf-8')) if sources_path.exists() else {'version': '0.1', 'tracks': []}
    sources['tracks'] = [t for t in sources.get('tracks', []) if t.get('file') != name] + [record]
    sources_path.write_text(json.dumps(sources, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    rel = f'public/music/{name}'
    return {'status': 'added', 'file': rel, 'src': f'music/{name}', 'song': summary(song), 'bytes': len(data),
            'note': 'Personal use only: keep it out of templates and packages, and say so in the delivery.',
            'next': run('npm', 'run', 'beats', '--', rel, cwd=root,
                        then=f'Set inputs.json props.music.src to "music/{name}", then validate and sample.')}


def doctor(_args):
    try:
        load_musicdl()
    except SongError as error:
        return {'status': 'passed', 'musicdl': 'missing', 'next': error.step}
    return {'status': 'passed', 'musicdl': 'installed', 'version': getattr(sys.modules.get('musicdl'), '__version__', None),
            'license': 'noncommercial; the songs belong to their rights holders'}


def main(argv=None):
    parser = argparse.ArgumentParser(prog='vvv_song.py', description=__doc__.split('\n')[0])
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor', help='Is musicdl installed?')
    s = sub.add_parser('search', help='Find recordings of a song.')
    s.add_argument('--keyword', required=True)
    s.add_argument('--source', action='append', help='musicdl client name, e.g. NeteaseMusicClient (repeatable).')
    s.add_argument('--limit', type=int, default=5, choices=range(1, 21), metavar='1-20')
    a = sub.add_parser('add', help='Download one recording into a project, for personal use.')
    a.add_argument('--project', required=True)
    a.add_argument('--keyword', required=True)
    a.add_argument('--source', required=True)
    a.add_argument('--id', required=True)
    a.add_argument('--name', help='File name after "personal-" (default: the song title).')
    a.add_argument('--personal-use', action='store_true', help='The user asked for this song for their own, noncommercial film.')
    args = parser.parse_args(argv)
    try:
        result = {'doctor': doctor, 'search': search, 'add': add}[args.command](args)
    except SongError as error:
        result = {'status': 'failed', 'code': error.code, 'message': error.message}
        if error.step:
            result['next'] = error.step
    except Exception as error:  # musicdl raises its own errors from network and parsing
        result = {'status': 'failed', 'code': 'MUSICDL_ERROR', 'message': f'musicdl failed: {error}'.strip(),
                  'next': fix('Try another source, or ask the user for the song as a file.')}
    emit(result)
    return 1 if result.get('status') == 'failed' else 0


if __name__ == '__main__':
    sys.exit(main())

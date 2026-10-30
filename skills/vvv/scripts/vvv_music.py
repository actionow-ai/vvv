"""A soundtrack in a project: add the user's file in one step, then fit the song to the template.

`add` copies the file into public/music, measures its beats with the project's analyzer, records it in
sources.json as the owner's and points the inputs at it. `fit` reads the template's timeline (pages in
beats, the climax page, the pace range) from the catalog and chooses where the song starts and how
slow the pages run, so the chorus opens the climax page, holds are long enough to watch and the film
ends inside the song. It writes the choice to inputs.json only with --apply.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess

from vvv_project import read_json, write_json

AUDIO = {'.mp3', '.m4a', '.aac', '.wav', '.ogg', '.flac'}
# The beat clock (core/beat-clock.ts) makes beat 0 the first beat at least LEAD_IN after the trim.
LEAD_IN = 0.35
# Trimming this far before a beat makes that beat the film's beat 0.
BEFORE_BEAT = 0.53
TAIL = 1.4
MIN_HOLD = 5.0


def project_root(project):
    root = Path(project).expanduser().resolve()
    if not (root / 'inputs.json').is_file() or not (root / 'public').is_dir():
        raise ValueError('INVALID_PROJECT: Use a project created by vvv.py init.')
    return root


def slug(text):
    value = re.sub(r'[^\w]+', '-', text, flags=re.UNICODE).strip('-').lower()
    return value[:60] or 'song'


def add(project, file, name=None, use=True):
    root = project_root(project)
    source = Path(file).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() not in AUDIO:
        raise ValueError(f'MUSIC_FILE: {file} is not a local audio file ({", ".join(sorted(AUDIO))}).')
    folder = root / 'public' / 'music'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f'{slug(name or source.stem)}{source.suffix.lower()}'
    if target.exists() and hashlib.sha256(target.read_bytes()).digest() != hashlib.sha256(source.read_bytes()).digest():
        raise ValueError(f'FILE_EXISTS: public/music/{target.name} already exists with other content; pass --name.')
    shutil.copyfile(source, target)
    beats_path = target.with_suffix('.beats.json')
    node = shutil.which('node')
    analyzer = root / 'scripts' / 'analyze-music.mjs'
    if not node or not analyzer.is_file():
        raise ValueError('NODE_MISSING: Measuring beats needs Node.js and the project scripts; run vvv.py doctor.')
    process = subprocess.run([node, str(analyzer), str(target), str(beats_path)], cwd=root, capture_output=True,
                             text=True, timeout=900, check=False)
    if process.returncode or not beats_path.is_file():
        raise ValueError('BEATS_FAILED: ' + (process.stderr or process.stdout)[-600:].strip())
    data = target.read_bytes()
    sources_path = folder / 'sources.json'
    sources = read_json(sources_path) if sources_path.is_file() else {'version': '0.1', 'tracks': []}
    beat_map = read_json(beats_path)
    record = {'file': target.name, 'title': name or source.stem, 'author': 'Supplied by the project owner',
              'source': f'Owner-supplied file {source.name}',
              'license': 'Supplied by the project owner for this film; rights stay with the rights holders.',
              'distribution': 'owner', 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
              'bpm': beat_map.get('bpm')}
    sources['tracks'] = [t for t in sources.get('tracks', []) if t.get('file') != target.name] + [record]
    write_json(sources_path, sources)
    if use:
        inputs = read_json(root / 'inputs.json')
        music = inputs['props'].setdefault('music', {})
        music.update({'src': f'music/{target.name}', 'trimBeforeSec': 0})
        music.setdefault('volume', 1)
        music.setdefault('fadeInSec', 0.3)
        music.setdefault('fadeOutSec', 3)
        write_json(root / 'inputs.json', inputs)
    return {'status': 'added', 'src': f'music/{target.name}', 'bpm': beat_map.get('bpm'),
            'seconds': beat_map.get('duration'), 'beats': len(beat_map.get('beats', [])), 'used': use}


def chorus_beat(beat_map):
    """The downbeat where the energy rises into its first sustained high: usually the first chorus."""
    energy, beats = beat_map.get('energy') or [], beat_map.get('beats') or []
    n = min(len(energy), len(beats))
    if n < 48:
        return None
    mean = lambda a, b: sum(energy[a:b]) / max(1, b - a)
    rise = lambda b: mean(b, b + 16) - mean(b - 16, b)
    downbeats = {round(t, 3) for t in beat_map.get('downbeats') or []}
    starts = [b for b in range(16, n - 16) if not downbeats or round(beats[b], 3) in downbeats]
    if not starts:
        return None
    peak = max(mean(b, b + 16) for b in starts)
    high = [b for b in starts if mean(b, b + 16) >= 0.85 * peak]
    # the strongest rise into the first high stretch, not a later repeat of the chorus
    window = [b for b in high if b <= high[0] + 16] if high else starts
    return max(window, key=rise)


def page_lengths(timeline, pace):
    """The template's page lengths at a pace: whole bars, never under one bar (as in the template code)."""
    return [(p['id'], max(4, math.floor(p['beats'] * pace / 4 + 0.5) * 4)) for p in timeline['pages']]


def beat_time(beats, i):
    if i < len(beats):
        return beats[i]
    period = (beats[-1] - beats[0]) / max(1, len(beats) - 1)
    return beats[-1] + (i - len(beats) + 1) * period


def fit(project, climax=None, seconds=None, apply=False):
    root = project_root(project)
    inputs = read_json(root / 'inputs.json')
    props, template = inputs['props'], inputs['template']
    catalog = read_json(root / 'catalog' / f'{template}.json')
    timeline = catalog.get('timeline')
    if not isinstance(timeline, dict) or not timeline.get('pages'):
        raise ValueError(f'TIMELINE_UNKNOWN: {template} declares no page timeline; set trimBeforeSec by ear from the beat map.')
    src = (props.get('music') or {}).get('src')
    if not src:
        raise ValueError('MUSIC_MISSING: Add a track first (vvv.py music add).')
    beats_path = root / 'public' / Path(src).with_suffix('.beats.json')
    if not beats_path.is_file():
        raise ValueError(f'BEATS_MISSING: {beats_path.relative_to(root)} is missing; run npm run beats -- public/{src}.')
    beat_map = read_json(beats_path)
    beats, duration = beat_map['beats'], beat_map.get('duration') or beat_map['beats'][-1]
    period = (beats[-1] - beats[0]) / max(1, len(beats) - 1)
    ids = [p['id'] for p in timeline['pages']]
    climax = climax or timeline.get('climax')
    if climax not in ids:
        raise ValueError(f'UNKNOWN_PAGE: {climax}; pages are {", ".join(ids)}.')
    chorus = chorus_beat(beat_map)
    pace_spec = timeline.get('pace') or {}
    low, high = float(pace_spec.get('min', 1)), float(pace_spec.get('max', 1))
    paces = sorted({round(low + 0.05 * k, 2) for k in range(int(round((high - low) / 0.05)) + 1)} | {low, high})

    plans = []
    for pace in paces:
        pages = page_lengths(timeline, pace)
        before = sum(n for _, n in pages[:ids.index(climax)])
        total = sum(n for _, n in pages)
        ideal = (chorus - before) if chorus is not None else 0
        # Land the climax page on the chorus, or as close as a valid start allows (within two beats).
        for first in sorted(range(max(0, ideal - 2), ideal + 3), key=lambda f: abs(f - ideal)):
            trim = max(0.0, beats[first] - BEFORE_BEAT)
            # beat 0 of the film must be this song beat: at least LEAD_IN after the trim, its predecessor not
            if beats[first] - trim < LEAD_IN or (first > 0 and beats[first - 1] - trim >= LEAD_IN):
                continue
            end = beat_time(beats, first + total) + TAIL
            if end > duration:
                continue
            holds, cursor = [], first
            for _, n in pages:
                holds.append(beat_time(beats, cursor + n) - beat_time(beats, cursor))
                cursor += n
            hold = min(holds)
            film = end - trim
            offset = first - ideal
            rushed = max(0.0, MIN_HOLD - hold)
            score = (abs(film - seconds) + 2 * rushed if seconds else 10 * rushed + (pace - low)) + 2 * abs(offset)
            plans.append({'score': score, 'pace': pace, 'trim': round(trim, 3), 'film': film, 'end': end,
                          'pages': pages, 'first': first, 'offset': offset})
            break
    if not plans:
        raise ValueError('FIT_IMPOSSIBLE: No start and pace put the chorus on that page and end inside the song; '
                         'choose another climax page or a longer track.')
    best = min(plans, key=lambda p: p['score'])
    schedule, cursor = [], best['first']
    for pid, n in best['pages']:
        t0 = beat_time(beats, cursor) - best['trim']
        t1 = beat_time(beats, cursor + n) - best['trim']
        schedule.append({'page': pid, 'beats': n, 'from': round(t0, 1), 'seconds': round(t1 - t0, 1)})
        cursor += n
    result = {'status': 'passed', 'bpm': beat_map.get('bpm'), 'chorusAt': round(beats[chorus], 2) if chorus is not None else None,
              'climax': climax, 'pace': best['pace'], 'trimBeforeSec': best['trim'],
              'filmSeconds': round(best['film'], 1), 'songFrom': round(best['trim'], 1), 'songTo': round(best['end'], 1),
              'shortestHold': min(s['seconds'] for s in schedule), 'pages': schedule, 'applied': apply,
              **({'chorusOffsetBeats': best['offset']} if best['offset'] else {}),
              'note': 'Tell the user the length and the seconds per page before rendering; holds under about 5 s feel rushed.'}
    if apply:
        music = props.setdefault('music', {})
        music['trimBeforeSec'] = best['trim']
        if best['trim'] > 0:
            music['fadeInSec'] = max(float(music.get('fadeInSec') or 0), 0.8)
        if pace_spec.get('prop'):
            props[pace_spec['prop']] = best['pace']
        write_json(root / 'inputs.json', inputs)
    return result


def timing(catalog, beat_map, pace=1.0):
    """Seconds per page and film length at a pace for a beat map, for describe."""
    timeline = catalog.get('timeline')
    if not isinstance(timeline, dict) or not timeline.get('pages') or not beat_map:
        return None
    beats = beat_map['beats']
    first = next((i for i, t in enumerate(beats) if t >= LEAD_IN), 0)
    cursor, pages = first, []
    for pid, n in page_lengths(timeline, pace):
        pages.append({'page': pid, 'beats': n, 'seconds': round(beat_time(beats, cursor + n) - beat_time(beats, cursor), 1)})
        cursor += n
    return {'bpm': beat_map.get('bpm'), 'pace': pace, 'filmSeconds': round(beat_time(beats, cursor) + TAIL, 1),
            'shortestHold': min(p['seconds'] for p in pages), 'pages': pages}

"""Measurable quality checks for a rendered video: frame size, sound, still holds and beat sync.

These checks find films that are silent, wrongly sized, frozen for long stretches or cut off the
beat. Passing them does not make a film good; the review checklist in the report still applies.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import tempfile
import wave

from PIL import Image

from vvv_media import MediaError, find_tool, probe_media, run_tool
from vvv_project import load_catalog, read_json, safe_output_path, safe_public_path, validate_project

# Frames are compared at a small size so film grain and sensor noise average out.
SAMPLE_SIZE = (48, 27)
# A frame is "still" when it barely differs from the frame half a second earlier. Comparing across
# half a second (not frame to frame) counts slow pushes and pans as motion. Calibrated on starter
# renders: a held photo with a 7% push reads 1-1.5, a frozen frame under film grain stays near 0.
STILL_LAG_SECONDS = 0.5
STILL_DIFFERENCE = 0.6
SILENCE_DBFS = -45.0
SYNC_PASS_MS = 66
REVIEW = [
    'The first three seconds give a reason to keep watching.',
    'Each beat has one main thing to read, and text stays on screen long enough to read it.',
    'Text is legible at phone size for the chosen format.',
    'Names, dates and captions match the photos and the supplied facts.',
    'The soundtrack suits the story, and its entry, exit and level work when listened to.',
]


def frame_sequence(ffmpeg, video, fps, folder):
    """Decode every frame (capped at 30 fps) to a tiny PNG; return grayscale byte strings."""
    rate = min(30.0, fps)
    pattern = str(Path(folder) / '%06d.png')
    run_tool([ffmpeg, '-v', 'error', '-nostdin', '-i', str(video), '-an', '-r', f'{rate:g}',
              '-s', f'{SAMPLE_SIZE[0]}x{SAMPLE_SIZE[1]}', '-f', 'image2', pattern], timeout=1800)
    frames = []
    for path in sorted(Path(folder).glob('*.png')):
        with Image.open(path) as image:
            frames.append(image.convert('L').tobytes())
    return frames, rate


def frame_changes(frames, lag=1):
    """Mean absolute difference between each frame and the frame `lag` frames earlier."""
    pixels = len(frames[0]) if frames else 1
    return [sum(abs(a - b) for a, b in zip(frames[i], frames[i - lag])) / pixels for i in range(lag, len(frames))]


def still_runs(drift, rate, minimum, lag=1):
    """Stretches where every frame matches the frame `lag` earlier. drift[k] compares frame k+lag with k."""
    runs, start = [], None
    for index, value in enumerate(drift + [math.inf]):
        if value < STILL_DIFFERENCE:
            start = index if start is None else start
        elif start is not None:
            first, last = start, index - 1 + lag
            seconds = (last - first) / rate
            if seconds >= minimum:
                runs.append({'from': round(first / rate, 2), 'to': round(last / rate, 2), 'seconds': round(seconds, 2)})
            start = None
    return runs


def visual_peaks(changes, rate, edge=0.5, gap=0.3):
    """Frames where the picture changes most, relative to their surroundings (cuts, entrances)."""
    smooth = [sum(changes[max(0, i - 1):i + 2]) / len(changes[max(0, i - 1):i + 2]) for i in range(len(changes))]
    if not smooth:
        return []
    top = max(smooth)
    end = len(changes) / rate
    peaks = []
    for i in range(3, len(smooth) - 3):
        if smooth[i] < max(smooth[i - 3:i + 4]):
            continue
        base = min(smooth[max(0, i - 30):i + 30])
        if smooth[i] >= 2.5 and smooth[i] >= base * 1.8 and smooth[i] >= 0.12 * top:
            # Smoothing spreads one cut over three equal values (exactly equal with Python 3.12's
            # compensated sum), so place it on the frame whose raw change is largest.
            j = max(range(i - 1, i + 2), key=changes.__getitem__)
            t = (j + 1) / rate
            if peaks and t - peaks[-1]['t'] < gap:
                if smooth[i] > peaks[-1]['s']:
                    peaks[-1] = {'t': t, 's': smooth[i]}
            else:
                peaks.append({'t': t, 's': smooth[i]})
    return [p for p in peaks if edge < p['t'] < end - edge]


def beat_sync(peaks, beats, offset, top=30):
    """Mean distance from the strongest visual changes to the nearest beat, in milliseconds."""
    times = [b - offset for b in beats]
    strongest = sorted(peaks, key=lambda p: p['s'], reverse=True)[:top]
    if not strongest or not times:
        return None
    distances = [min(abs(p['t'] - b) for b in times) for p in strongest]
    # The peaks furthest from a beat, signed (negative: before the beat), so a fix can target them.
    worst = []
    for peak in strongest:
        beat = min(range(len(times)), key=lambda i: abs(peak['t'] - times[i]))
        worst.append({'t': round(peak['t'], 2), 'beat': beat, 'beatAt': round(times[beat], 2),
                      'offsetMs': round(1000 * (peak['t'] - times[beat])), 'strength': round(peak['s'], 1)})
    worst = sorted(worst, key=lambda w: -abs(w['offsetMs']))[:8]
    return {'peaks': len(strongest), 'meanMs': round(1000 * sum(distances) / len(distances)),
            'within66ms': round(sum(d <= 0.066 for d in distances) / len(distances), 2),
            'worst': [w for w in worst if abs(w['offsetMs']) > 66]}


def audio_levels(ffmpeg, video, folder):
    target = Path(folder) / 'audio.wav'
    run_tool([ffmpeg, '-v', 'error', '-nostdin', '-i', str(video), '-vn', '-ac', '1', '-ar', '8000',
              '-acodec', 'pcm_s16le', '-f', 'wav', str(target)], timeout=600)
    with wave.open(str(target), 'rb') as audio:
        rate = audio.getframerate()
        data = audio.readframes(audio.getnframes())
    samples = memoryview(data).cast('h')
    window = rate // 2
    def dbfs(chunk):
        if not len(chunk):
            return -math.inf
        power = sum(s * s for s in chunk) / len(chunk)
        return 10 * math.log10(power / 32768 ** 2) if power else -math.inf
    windows = [dbfs(samples[i:i + window]) for i in range(0, len(samples), window)]
    silent, longest = 0, 0
    for level in windows:
        silent = silent + 1 if level < SILENCE_DBFS else 0
        longest = max(longest, silent)
    overall = dbfs(samples)
    return {'meanDbfs': round(overall, 1) if math.isfinite(overall) else None,
            'longestSilenceSeconds': longest * window / rate}


def check_video(video, ffmpeg, ffprobe, expected=None, max_still=3.0, music_required=False,
                beats=None, beat_offset=0.0):
    checks = []
    def add(code, status, message, **details):
        checks.append({'code': code, 'status': status, 'message': message, **details})

    metadata = probe_media(ffprobe, video)
    videos = [s for s in metadata['streams'] if s.get('codec_type') == 'video']
    audios = [s for s in metadata['streams'] if s.get('codec_type') == 'audio']
    if not videos:
        raise MediaError('invalid_media', 'The file has no video stream.')
    stream = videos[0]
    width, height = int(stream.get('width') or 0), int(stream.get('height') or 0)
    try:
        num, den = (stream.get('avg_frame_rate') or stream.get('r_frame_rate') or '30/1').split('/')
        fps = float(num) / float(den)
    except (ValueError, ZeroDivisionError):
        fps = 30.0
    summary = {'width': width, 'height': height, 'fps': round(fps, 3), 'durationSeconds': metadata['durationSeconds']}

    if expected:
        ew, eh = expected
        same_shape = width and height and abs(width / height - ew / eh) < 0.01
        add('FORMAT', 'passed' if same_shape else 'failed',
            f'Frame is {width}×{height}; the project format is {ew}×{eh}.')
    short = min(width, height)
    add('RESOLUTION', 'passed' if short >= 1080 else 'warning',
        f'Short side is {short}px; review delivery quality at 1080px or more.' if short < 1080 else f'Short side is {short}px.')

    with tempfile.TemporaryDirectory(prefix='vvv-check-') as folder:
        if not audios:
            add('AUDIO', 'failed' if music_required else 'warning', 'The video has no audio track.')
        else:
            levels = audio_levels(ffmpeg, video, folder)
            quiet = levels['meanDbfs'] is None or levels['meanDbfs'] < SILENCE_DBFS
            add('AUDIO', 'failed' if quiet else 'passed',
                'The audio track is silent.' if quiet else f"Mean level {levels['meanDbfs']} dBFS.", **levels)

        frames, rate = frame_sequence(ffmpeg, video, fps, Path(folder))
        if len(frames) < 2:
            raise MediaError('invalid_media', 'Too few decodable frames to measure motion.')
        changes = frame_changes(frames)
        lag = max(1, round(rate * STILL_LAG_SECONDS))
        drift = frame_changes(frames, lag) if len(frames) > lag else changes
        runs = still_runs(drift, rate, max_still, lag if len(frames) > lag else 1)
        still_share = sum(c < STILL_DIFFERENCE for c in drift) / len(drift)
        add('STILL', 'failed' if runs else 'passed',
            f'{len(runs)} still stretch(es) longer than {max_still:g}s.' if runs else
            f'No still stretch longer than {max_still:g}s.',
            runs=runs, stillShare=round(still_share, 2))

        if beats:
            sync = beat_sync(visual_peaks(changes, rate), beats, beat_offset)
            if sync is None:
                add('BEAT_SYNC', 'warning', 'No clear visual cuts to compare with the beat map.')
            else:
                ok = sync['meanMs'] <= SYNC_PASS_MS
                add('BEAT_SYNC', 'passed' if ok else 'failed',
                    f"Strongest visual changes sit {sync['meanMs']} ms from the nearest beat on average.", **sync)
        elif music_required:
            add('BEAT_SYNC', 'warning', 'No beat map found for the soundtrack; cuts were not compared with the music.')

    failed = any(c['status'] == 'failed' for c in checks)
    return {'status': 'failed' if failed else 'passed', 'video': summary, 'checks': checks,
            'review': REVIEW,
            'limits': 'Motion is measured as frame-to-frame change; grain or noise overlays can hide a frozen subject.'}


def latest_output(project):
    reports = []
    for path in (project / 'out').glob('*.report.json'):
        try:
            report = read_json(path)
            if isinstance(report, dict) and report.get('mode') in ('sample', 'render') and report.get('output'):
                reports.append(report)
        except (OSError, ValueError):
            continue
    if not reports:
        raise ValueError('NO_RENDER: Render a sample or the full film first, or pass --video.')
    return max(reports, key=lambda r: r.get('createdAt', ''))


def read_beats(path, label):
    data = read_json(path)
    beats = data.get('beats') if isinstance(data, dict) else data
    if not isinstance(beats, list) or not all(isinstance(b, (int, float)) and not isinstance(b, bool)
                                              and math.isfinite(b) for b in beats):
        raise ValueError(f'BEATS_INVALID: {label}: expected {{"beats": [seconds, ...]}} or a list of seconds.')
    return beats


def check_project(project, video=None, ffmpeg=None, ffprobe=None):
    project = Path(project).expanduser().resolve()
    validation = validate_project(project)
    if validation['status'] == 'failed':
        failed = [c for c in validation['checks'] if c['status'] == 'failed']
        return {'status': 'failed', 'code': 'PROJECT_INVALID',
                'message': 'Fix the project before checking its video: ' +
                           '; '.join(f"{c['code']}: {c['message']}" for c in failed[:3]) + (' …' if len(failed) > 3 else ''),
                'validation': validation}
    inputs = read_json(project / 'inputs.json')
    catalog = load_catalog(project, inputs.get('template'))
    props = inputs.get('props', {})
    report = None
    if video is None:
        report = latest_output(project)
        video = safe_output_path(project, report['output'])
    video = Path(video).expanduser().resolve()
    if not video.is_file():
        raise ValueError(f'VIDEO_MISSING: {video}')
    size = catalog['formats'][props.get('format', catalog['defaultFormat'])]
    music = props.get('music', {}) if isinstance(props.get('music'), dict) else {}
    trim = music.get('trimBeforeSec')
    trim = float(trim) if isinstance(trim, (int, float)) and not isinstance(trim, bool) and math.isfinite(trim) else 0.0

    def beat_times(src):
        relative = src.rsplit('.', 1)[0] + '.beats.json'
        try:
            beat_file = safe_public_path(project, relative)
        except ValueError as error:
            raise ValueError(f'BEATS_INVALID: public/{relative}: {error}') from None
        return read_beats(beat_file, f'public/{relative}') if beat_file.is_file() else None

    beats = None
    if music.get('src'):
        first = beat_times(music['src'])
        if first is not None:
            # Film-time beats: the first track, then each later track the catalog declares
            # ({"src", "at": film second its file starts, "from": film second it takes over}).
            beats = [b - trim for b in first]
            for extra in catalog.get('check', {}).get('tracks', []):
                more = beat_times(extra['src'])
                if more is None:
                    continue
                beats = [b for b in beats if b < extra['from']] + [b + extra['at'] for b in more if b + extra['at'] >= extra['from']]
    offset = 0.0
    if report:
        # Video time = film time - the sample's start in the film.
        offset += float(report.get('sourceTimeRange', {}).get('from', 0))
    result = check_video(
        video,
        find_tool('ffmpeg', ffmpeg, project),
        find_tool('ffprobe', ffprobe, project),
        expected=(size['width'], size['height']),
        max_still=float(catalog.get('check', {}).get('maxStillSeconds', 3)),
        music_required=bool(catalog.get('music', {}).get('required')),
        beats=beats,
        beat_offset=offset,
    )
    result['source'] = {'video': str(video), 'report': report.get('output') if report else None,
                        'format': props.get('format', catalog['defaultFormat'])}
    return result


def check_file(video, beats_file=None, max_still=3.0, ffmpeg=None, ffprobe=None):
    """Measure any video, such as a reference film, without a project: no format expectation;
    beats come from a beat map such as one written by the kit's `npm run beats`."""
    video = Path(video).expanduser().resolve()
    if not video.is_file():
        raise ValueError(f'VIDEO_MISSING: {video}')
    beats = None
    if beats_file is not None:
        beats = read_beats(Path(beats_file).expanduser(), Path(beats_file).name)
    here = Path.cwd()
    result = check_video(video, find_tool('ffmpeg', ffmpeg, here), find_tool('ffprobe', ffprobe, here),
                         max_still=max_still, beats=beats)
    result['source'] = {'video': str(video), 'beats': str(beats_file) if beats_file else None}
    return result

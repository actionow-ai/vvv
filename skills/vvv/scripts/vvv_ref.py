#!/usr/bin/env python3
"""Tools for studying a reference film and comparing a rebuild with it.

  sheet   --video V --output OUT.jpg (--from S --to E --step D | --at T ...) [--width PX] [--columns N]
          a contact sheet of frames, each labelled with its time; use a 0.1 s step around transitions
  layout  --video V --at T [--at T ...] [--min-area PX]
          the photo boxes and the text/decoration extent of settled frames, in frame pixels
  compare --a REF --b NEW --pair TA:TB [--pair ...] --output OUT.jpg [--width PX]
          reference and rebuild side by side, one row per pair of times (match them by beat)

Frames are decoded with FFmpeg one at a time and tiled with Pillow, so Remotion's reduced FFmpeg is
enough. The strongest visual changes and their distance from the beat are in `vvv.py check`.
"""
from __future__ import annotations

import argparse
from collections import deque
import io
from pathlib import Path
import sys

from vvv import emit, fix
from vvv_media import MediaError, find_tool

MAX_FRAMES = 120


def frame(ffmpeg, video, at):
    """One decoded frame at `at` seconds as a Pillow image."""
    from PIL import Image
    data = run_tool_bytes([ffmpeg, '-v', 'error', '-nostdin', '-ss', f'{at:.3f}', '-i', str(video), '-frames:v', '1',
                           '-f', 'image2pipe', '-vcodec', 'mjpeg', '-q:v', '3', '-'])
    if not data:
        raise MediaError('no_frame', f'No frame at {at:.2f} s; is it past the end?')
    return Image.open(io.BytesIO(data)).convert('RGB')


def run_tool_bytes(command):
    import subprocess
    from vvv_media import library_env
    process = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, env=library_env(command[0]),
                             timeout=120, check=False)
    if process.returncode:
        raise MediaError('processing_failed', process.stderr.decode('utf-8', 'replace')[-600:].strip())
    return process.stdout


def times(args):
    if args.at:
        values = list(args.at)
    else:
        if args.start is None or args.end is None or not args.step:
            raise MediaError('bad_request', 'Pass --at times, or --from, --to and --step.')
        values, t = [], args.start
        while t < args.end - 1e-9:
            values.append(round(t, 3))
            t += args.step
    if not values or len(values) > MAX_FRAMES:
        raise MediaError('bad_request', f'Ask for 1 to {MAX_FRAMES} frames per sheet.')
    return values


def labelled(image, text, width):
    from PIL import ImageDraw
    image = image.resize((width, round(image.height * width / image.width)))
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, 9 * len(text) + 8, 18], fill=(0, 0, 0))
    draw.text((4, 3), text, fill=(255, 80, 80))
    return image


def tile(images, columns, gap=6):
    from PIL import Image
    w = max(i.width for i in images)
    h = max(i.height for i in images)
    rows = (len(images) + columns - 1) // columns
    sheet = Image.new('RGB', (columns * w + (columns - 1) * gap, rows * h + (rows - 1) * gap), (24, 24, 24))
    for n, image in enumerate(images):
        sheet.paste(image, ((n % columns) * (w + gap), (n // columns) * (h + gap)))
    return sheet


def output_path(value):
    path = Path(value).expanduser().resolve()
    if path.suffix.lower() not in ('.jpg', '.jpeg', '.png'):
        raise MediaError('bad_request', 'Write the sheet as .jpg or .png.')
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def sheet(args):
    ffmpeg = find_tool('ffmpeg', args.ffmpeg, Path(args.video).parent)
    at = times(args)
    images = [labelled(frame(ffmpeg, args.video, t), f'{t:.2f}', args.width) for t in at]
    out = output_path(args.output)
    tile(images, args.columns).save(out, quality=88)
    return {'status': 'passed', 'output': str(out), 'frames': len(at), 'from': at[0], 'to': at[-1],
            'note': 'Open the sheet and describe what moves: entrances, exits, transitions, text reveals.'}


def regions(image, min_area):
    """Large non-paper regions (photos) and the extent of small marks (text, line art), in frame pixels."""
    rgb = image.convert('RGB')
    w, h = rgb.size
    s = 4
    small = rgb.resize((w // s, h // s))
    sw, sh = small.size
    px = small.load()
    border = [px[x, 0] for x in range(sw)] + [px[x, sh - 1] for x in range(sw)] + [px[0, y] for y in range(sh)] + [px[sw - 1, y] for y in range(sh)]
    # Paper is the most common edge colour: flat, while photo edges spread over many shades.
    counts = {}
    for c in border:
        key = tuple(v // 8 for v in c)
        counts[key] = counts.get(key, 0) + 1
    # Prefer a light colour holding a fair share of the edge: a photo can own more of the edge than the paper.
    light = {k: n for k, n in counts.items() if sum(k) * 8 >= 600 and n >= 0.15 * len(border)}
    paper = tuple(v * 8 + 4 for v in max(light or counts, key=(light or counts).get))
    if sum(paper) < 600:  # only dark edges: treat white as paper
        paper = (255, 255, 255)
    mask = [[max(abs(px[x, y][i] - paper[i]) for i in range(3)) > 28 for x in range(sw)] for y in range(sh)]
    seen = [[False] * sw for _ in range(sh)]
    photos, marks = [], []
    for y in range(sh):
        for x in range(sw):
            if not mask[y][x] or seen[y][x]:
                continue
            queue, seen[y][x] = deque([(x, y)]), True
            x0 = x1 = x
            y0 = y1 = y
            count = 0
            while queue:
                cx, cy = queue.popleft()
                count += 1
                x0, x1, y0, y1 = min(x0, cx), max(x1, cx), min(y0, cy), max(y1, cy)
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < sw and 0 <= ny < sh and mask[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = True
                        queue.append((nx, ny))
            box = {'x': x0 * s, 'y': y0 * s, 'w': (x1 - x0 + 1) * s, 'h': (y1 - y0 + 1) * s}
            if box['w'] * box['h'] >= min_area and count * s * s >= 0.5 * box['w'] * box['h']:
                photos.append(box)
            elif count >= 3:
                marks.append(box)
    photos.sort(key=lambda b: (b['y'] // 40, b['x']))
    extent = None
    if marks:
        extent = {'x': min(b['x'] for b in marks), 'y': min(b['y'] for b in marks)}
        extent.update(w=max(b['x'] + b['w'] for b in marks) - extent['x'], h=max(b['y'] + b['h'] for b in marks) - extent['y'])
    return {'size': [w, h], 'paper': '#%02x%02x%02x' % paper, 'photos': photos, 'marks': len(marks), 'markExtent': extent}


def layout(args):
    ffmpeg = find_tool('ffmpeg', args.ffmpeg, Path(args.video).parent)
    frames = [{'at': t, **regions(frame(ffmpeg, args.video, t), args.min_area)} for t in args.at]
    return {'status': 'passed', 'frames': frames,
            'note': 'Measure settled frames (after entrances, before exits). Photos are filled boxes; marks are text and line art.'}


def compare(args):
    ffmpeg_a = find_tool('ffmpeg', args.ffmpeg, Path(args.a).parent)
    pairs = []
    for value in args.pair:
        try:
            ta, tb = (float(p) for p in value.split(':'))
        except ValueError:
            raise MediaError('bad_request', f'--pair takes REF_SECONDS:NEW_SECONDS, not {value!r}.') from None
        pairs.append((ta, tb))
    if not pairs or len(pairs) > 40:
        raise MediaError('bad_request', 'Pass 1 to 40 --pair values.')
    images = []
    for ta, tb in pairs:
        images.append(labelled(frame(ffmpeg_a, args.a, ta), f'ref {ta:.2f}', args.width))
        images.append(labelled(frame(ffmpeg_a, args.b, tb), f'new {tb:.2f}', args.width))
    out = output_path(args.output)
    tile(images, 2).save(out, quality=88)
    return {'status': 'passed', 'output': str(out), 'pairs': len(pairs),
            'note': 'Compare composition, crop, text size and hierarchy row by row; then play both at the transitions.'}


def main(argv=None):
    parser = argparse.ArgumentParser(prog='vvv_ref.py', description=__doc__.split('\n')[0])
    sub = parser.add_subparsers(dest='command', required=True)
    s = sub.add_parser('sheet', help='Contact sheet of frames.')
    s.add_argument('--video', required=True)
    s.add_argument('--output', required=True)
    s.add_argument('--at', type=float, action='append')
    s.add_argument('--from', dest='start', type=float)
    s.add_argument('--to', dest='end', type=float)
    s.add_argument('--step', type=float)
    s.add_argument('--width', type=int, default=400)
    s.add_argument('--columns', type=int, default=6)
    s.add_argument('--ffmpeg')
    lay = sub.add_parser('layout', help='Photo boxes and text extent of settled frames.')
    lay.add_argument('--video', required=True)
    lay.add_argument('--at', type=float, action='append', required=True)
    lay.add_argument('--min-area', dest='min_area', type=int, default=40000, help='Smallest photo box in square pixels.')
    lay.add_argument('--ffmpeg')
    c = sub.add_parser('compare', help='Reference and rebuild side by side.')
    c.add_argument('--a', required=True, help='The reference video.')
    c.add_argument('--b', required=True, help='The rebuild.')
    c.add_argument('--pair', action='append', required=True, help='REF_SECONDS:NEW_SECONDS (repeatable).')
    c.add_argument('--output', required=True)
    c.add_argument('--width', type=int, default=640)
    c.add_argument('--ffmpeg')
    args = parser.parse_args(argv)
    try:
        for name in ('video', 'a', 'b'):
            value = getattr(args, name, None)
            if value and not Path(value).expanduser().is_file():
                raise MediaError('invalid_source', f'{value} is not a local file.')
        result = {'sheet': sheet, 'layout': layout, 'compare': compare}[args.command](args)
    except MediaError as error:
        result = {'status': 'failed', 'code': str(error.code).upper(), 'message': str(error),
                  'next': fix('Check the paths and times; run vvv.py doctor if FFmpeg is missing.')}
    except ImportError:
        result = {'status': 'failed', 'code': 'DEPENDENCY_MISSING', 'message': 'Pillow is required.',
                  'next': fix('Install the skill requirements (pip install -r requirements.txt).')}
    emit(result)
    return 1 if result.get('status') == 'failed' else 0


if __name__ == '__main__':
    sys.exit(main())

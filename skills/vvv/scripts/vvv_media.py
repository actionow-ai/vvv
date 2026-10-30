#!/usr/bin/env python3
"""Offline media inspection and extraction. Originals and project slots are never edited."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import uuid
import wave

from PIL import Image, UnidentifiedImageError


class MediaError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class JSONParser(argparse.ArgumentParser):
    def error(self, message):
        raise MediaError('invalid_arguments', message)


def parser():
    result = JSONParser(description=__doc__)
    commands = result.add_subparsers(dest='operation', required=True)
    for name in ('doctor', 'probe', 'clip', 'audio', 'frames'):
        command = commands.add_parser(name)
        command.add_argument('--project', required=True, help='An existing local project directory.')
        command.add_argument('--ffmpeg', help='Explicit FFmpeg executable; never installed automatically.')
        command.add_argument('--ffprobe', help='Explicit FFprobe executable.')
        if name != 'doctor':
            command.add_argument('--source', required=True, help='A regular local file, relative to the current directory or absolute.')
        if name in ('clip', 'audio'):
            command.add_argument('--from', dest='start', required=name == 'clip')
            command.add_argument('--to', dest='end', required=name == 'clip')
            command.add_argument('--audio-stream', default='0', help='Zero-based audio stream ordinal, a:N (default 0).')
        if name == 'clip':
            command.add_argument('--mute', action='store_true')
        if name == 'frames':
            command.add_argument('--at', action='append', required=True, help='Seconds; repeat up to 24 times.')
    return result


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def local_source(value):
    if re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', value) and not re.match(r'^[A-Za-z]:[\\/]', value):
        raise MediaError('source_not_local', 'Use a local file; URLs and FFmpeg protocols are not accepted.')
    # Check before resolving: resolving would conceal symlinks in parent directories.
    path = Path(value).expanduser().absolute()
    # macOS exposes normal temporary files through these two OS-owned aliases.
    # Normalize only their exact system targets; user-created symlinks stay rejected.
    if sys.platform == 'darwin' and len(path.parts) > 1 and path.parts[1] in ('tmp', 'var'):
        alias = Path('/') / path.parts[1]
        target = Path('/private') / path.parts[1]
        if alias.is_symlink() and alias.resolve() == target:
            path = Path('/private') / path.relative_to('/')
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise MediaError('source_symlink', 'Source files and their parent directories must not be symbolic links.')
    if not path.exists():
        raise MediaError('source_missing', 'Source file does not exist.')
    if not path.is_file():
        raise MediaError('source_not_file', 'Source must be a regular local file.')
    return path.resolve()


def seconds(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise MediaError('invalid_time', 'Times must be finite, non-negative seconds.')
    if not math.isfinite(result) or result < 0:
        raise MediaError('invalid_time', 'Times must be finite, non-negative seconds.')
    return result


def request_data(args):
    result = {'operation': args.operation}
    if args.operation in ('clip', 'audio'):
        start = seconds(args.start) if args.start is not None else 0.0
        end = seconds(args.end) if args.end is not None else None
        if end is not None and end <= start:
            raise MediaError('invalid_time', '--to must be greater than --from; ranges are [from, to).')
        if not re.fullmatch(r'\d+', args.audio_stream):
            raise MediaError('invalid_stream', '--audio-stream must be a non-negative audio ordinal (a:N).')
        result.update({'from': start, 'to': end, 'audioStream': int(args.audio_stream)})
        if args.operation == 'clip':
            result['mute'] = args.mute
    if args.operation == 'frames':
        if len(args.at) > 24:
            raise MediaError('too_many_frames', 'Request at most 24 frame timestamps per job.')
        result['at'] = [seconds(value) for value in args.at]
    return result


def compositor_tool(name, project):
    """Remotion's bundled binary, e.g. compositor-darwin-arm64, compositor-linux-x64-gnu or -musl,
    compositor-win32-x64-msvc."""
    system = {'Darwin': 'darwin', 'Linux': 'linux', 'Windows': 'win32'}.get(platform.system())
    architecture = {'arm64': 'arm64', 'aarch64': 'arm64', 'x86_64': 'x64', 'AMD64': 'x64'}.get(platform.machine())
    if not system or not architecture:
        raise MediaError('tool_missing', '%s not found; provide --%s.' % (name, name))
    executable = name + ('.exe' if system == 'win32' else '')
    folders = sorted((Path(project) / 'node_modules' / '@remotion').glob('compositor-%s-%s*' % (system, architecture)))
    return next((f / executable for f in folders if (f / executable).is_file()),
                folders[0] / executable if folders else Path(project) / 'node_modules' / '@remotion' / executable)


def default_kit():
    """The kit beside this skill or in $VVV_KIT; its renderer install carries Remotion's FFmpeg."""
    if os.environ.get('VVV_KIT'):
        return Path(os.environ['VVV_KIT']).expanduser()
    return Path(__file__).resolve().parents[3] / 'kits' / 'remotion'


def find_tool(name, explicit, project):
    """An explicit path, then PATH, then Remotion's FFmpeg in the project, then in the kit."""
    if explicit:
        candidate = Path(explicit).expanduser()
    elif shutil.which(name):
        candidate = Path(shutil.which(name))
    else:
        candidate = compositor_tool(name, project)
        kit = default_kit()
        if not candidate.is_file() and (kit / 'node_modules').is_dir():
            candidate = compositor_tool(name, kit)
    if not candidate.is_file():
        raise MediaError('tool_missing', '%s not found; install it yourself or provide --%s.' % (name, name))
    if not os.access(candidate, os.X_OK):
        raise MediaError('tool_unavailable', '%s exists but is not executable.' % name)
    return str(candidate.resolve())


def library_env(executable, env=None):
    """Remotion's compositor binaries load the libav* libraries beside them (libavdevice.dylib on macOS)."""
    env = dict(os.environ if env is None else env)
    folder = Path(executable).parent
    variable = {'darwin': 'DYLD_LIBRARY_PATH', 'linux': 'LD_LIBRARY_PATH'}.get(
        'linux' if sys.platform.startswith('linux') else sys.platform)
    if variable and (folder.name.startswith('compositor-') or list(folder.glob('libav*'))):
        previous = env.get(variable)
        env[variable] = str(folder) + (os.pathsep + previous if previous else '')
    return env


def run_tool(command, timeout=600, code='processing_failed'):
    env = library_env(command[0])
    try:
        process = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                                 text=True, env=env, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        raise MediaError('tool_timeout', '%s exceeded the local processing timeout.' % Path(command[0]).name)
    except OSError as error:
        raise MediaError('tool_unavailable', 'Cannot run %s: %s' % (Path(command[0]).name, error))
    if process.returncode:
        raise MediaError(code, '%s failed: %s' % (Path(command[0]).name, process.stderr[-2000:].strip()))
    return process.stdout


def tool_details(executable):
    text = run_tool([executable, '-version'], timeout=20, code='tool_unavailable')
    return {'path': executable, 'version': text.splitlines()[0] if text.strip() else 'unknown'}


def capabilities(ffmpeg):
    encoders_text = run_tool([ffmpeg, '-hide_banner', '-encoders'], timeout=20, code='tool_unavailable')
    muxers_text = run_tool([ffmpeg, '-hide_banner', '-muxers'], timeout=20, code='tool_unavailable')
    encoders = set(re.findall(r'^\s*[VAS][A-Z.]{5}\s+(\S+)', encoders_text, re.MULTILINE))
    muxers = set()
    for line in muxers_text.splitlines():
        match = re.match(r'^\s+E[d.]?\s+(\S+)', line)
        if match:
            muxers.update(match.group(1).split(','))
    return encoders, muxers


def needed(operation, audio=True):
    return {
        'probe': (set(), set()),
        'clip': ({'libx264', 'rawvideo'} | ({'aac', 'pcm_s16le'} if audio else set()), {'mp4', 'null'}),
        'audio': ({'pcm_s16le'}, {'wav', 'null'}),
        'frames': ({'png'}, {'image2'}),
    }[operation]


def capability_result(operation, encoders, muxers, audio=True):
    enc, mux = needed(operation, audio)
    missing = sorted(['encoder:' + item for item in enc - encoders] + ['muxer:' + item for item in mux - muxers])
    return {'available': not missing, 'requiredEncoders': sorted(enc), 'requiredMuxers': sorted(mux), 'missing': missing}


def probe_media(ffprobe, source):
    value = run_tool([ffprobe, '-v', 'error', '-protocol_whitelist', 'file,pipe', '-show_entries',
                      'format=duration,format_name,size,start_time:stream=index,codec_name,codec_type,width,height,sample_aspect_ratio,display_aspect_ratio,r_frame_rate,avg_frame_rate,sample_rate,channels,channel_layout,duration,start_time,nb_frames:stream_disposition=attached_pic:stream_side_data=rotation,displaymatrix:stream_tags=rotate',
                      '-of', 'json', str(source)], timeout=60, code='invalid_media')
    try:
        result = json.loads(value)
        streams = result.get('streams', [])
        if not streams:
            raise ValueError('No media streams found.')
        duration = None
        for value in [result.get('format', {}).get('duration')]:
            try:
                candidate = float(value)
                if math.isfinite(candidate) and candidate > 0:
                    duration = candidate
            except (TypeError, ValueError):
                pass
        return {'durationSeconds': duration, 'format': result.get('format', {}), 'streams': streams}
    except (ValueError, TypeError, AttributeError) as error:
        raise MediaError('invalid_media', 'Cannot read media metadata: ' + str(error))


def select_streams(metadata, request):
    videos = [stream for stream in metadata['streams'] if stream.get('codec_type') == 'video'
              and not stream.get('disposition', {}).get('attached_pic')]
    audios = [stream for stream in metadata['streams'] if stream.get('codec_type') == 'audio']
    operation = request['operation']
    if operation in ('clip', 'frames') and not videos:
        raise MediaError('missing_video', 'No video stream other than attached cover art was found.')
    ordinal = request.get('audioStream', 0)
    wants_audio = operation == 'audio' or (operation == 'clip' and not request['mute'])
    if wants_audio and ordinal >= len(audios):
        if operation == 'audio' or ordinal != 0 or audios:
            raise MediaError('missing_audio', 'Requested audio stream a:%d was not found.' % ordinal)
    return (videos[0] if videos else None), (audios[ordinal] if wants_audio and ordinal < len(audios) else None)


def bounded_request(request, metadata):
    duration = metadata['durationSeconds']
    if duration is None:
        raise MediaError('duration_unknown', 'Source duration is unknown; cannot validate extraction bounds. Use an indexed local media file.')
    if request['operation'] == 'frames':
        if any(value >= duration for value in request['at']):
            raise MediaError('time_out_of_range', 'Frame times must be within [0, source duration).')
    else:
        if request['to'] is None:
            request['to'] = duration
        if request['from'] >= duration or request['to'] > duration:
            raise MediaError('time_out_of_range', 'Requested range exceeds source duration %.9g seconds.' % duration)


def safe_folder(project, relative):
    current = project
    for name in Path(relative).parts:
        current = current / name
        if current.is_symlink() or (current.exists() and not current.is_dir()):
            raise MediaError('output_unavailable', 'Output directories must be real directories: ' + relative)
        current.mkdir(exist_ok=True)
    return current


def write_record(path, record):
    temporary = path.parent / '.job.json.tmp'
    with temporary.open('x', encoding='utf-8', newline='\n') as output:
        json.dump(record, output, ensure_ascii=False, indent=2, allow_nan=False)
        output.write('\n')
    temporary.replace(path)


def validate_output(path, operation, ffprobe, ffmpeg):
    if not path.is_file() or path.stat().st_size == 0:
        raise MediaError('invalid_output', 'No non-empty media output was produced.')
    try:
        metadata = probe_media(ffprobe, path)
        if operation == 'frames':
            with Image.open(path) as image:
                image.load()
                if image.format != 'PNG' or min(image.size) < 1:
                    raise ValueError('Expected a non-empty PNG frame.')
        else:
            if metadata['durationSeconds'] is None:
                raise ValueError('Output duration is not measurable.')
            if operation == 'audio':
                with wave.open(str(path), 'rb') as audio:
                    if audio.getnframes() == 0 or audio.getsampwidth() != 2 or audio.getnchannels() < 1:
                        raise ValueError('Expected non-empty 16-bit PCM audio.')
            # Explicit raw/PCM encoders also work in Remotion's reduced FFmpeg build.
            run_tool([ffmpeg, '-v', 'error', '-nostdin', '-protocol_whitelist', 'file,pipe', '-i', str(path), '-map', '0:v:0?',
                      '-map', '0:a:0?', '-c:v', 'rawvideo', '-c:a', 'pcm_s16le', '-f', 'null', '-'],
                     code='invalid_output')
        return metadata
    except (OSError, ValueError, wave.Error, UnidentifiedImageError, Image.DecompressionBombError) as error:
        raise MediaError('invalid_output', 'Output did not pass decoding validation: ' + str(error))


def extract(ffmpeg, source, request, video, audio, staging):
    base = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin', '-n', '-protocol_whitelist', 'file,pipe']
    operation = request['operation']
    if operation == 'frames':
        files = []
        for index, at in enumerate(request['at'], 1):
            output = staging / ('frame-%03d.png' % index)
            run_tool(base + ['-accurate_seek', '-ss', str(at), '-i', str(source), '-map',
                             '0:' + str(video['index']), '-frames:v', '1', '-c:v', 'png',
                             '-an', '-sn', '-dn', '-map_metadata', '-1', '-f', 'image2', str(output)])
            files.append(output)
        return files
    command = base + ['-accurate_seek', '-ss', str(request['from']), '-i', str(source),
                      '-t', str(request['to'] - request['from'])]
    if operation == 'clip':
        output = staging / 'clip.mp4'
        command += ['-map', '0:' + str(video['index'])]
        if audio:
            command += ['-map', '0:a:' + str(request['audioStream']), '-c:a', 'aac']
        else:
            command += ['-an']
        pixel_format = 'yuv420p' if video.get('width', 0) % 2 == 0 and video.get('height', 0) % 2 == 0 else 'yuv444p'
        command += ['-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', pixel_format,
                    '-sn', '-dn', '-map_metadata', '-1', '-movflags', '+faststart', '-f', 'mp4', str(output)]
    else:
        output = staging / 'audio.wav'
        command += ['-map', '0:a:' + str(request['audioStream']), '-vn', '-sn', '-dn', '-c:a',
                    'pcm_s16le', '-map_metadata', '-1', '-f', 'wav', str(output)]
    run_tool(command)
    return [output]


def execute(args):
    record, record_path, staging, destination = None, None, None, None
    published = False
    try:
        project = Path(args.project).expanduser().resolve()
        if not project.is_dir():
            raise MediaError('project_missing', '--project must be an existing local directory.')
        request = request_data(args)
        if args.operation not in ('doctor', 'probe'):
            jobs = safe_folder(project, 'creative/media-jobs')
            identifier = str(uuid.uuid4())
            job = jobs / identifier
            job.mkdir(exist_ok=False)
            record_path = job / 'job.json'
            record = {'version': '1', 'id': identifier, 'status': 'running', 'createdAt': timestamp(),
                      'request': request, 'source': {'name': Path(args.source).name},
                      'tools': {}, 'outputs': [], 'visualReview': 'not-reviewed',
                      'strategy': {'seek': 'input-accurate-seek-and-reencode', 'timeRange': '[from,to)',
                                   'precision': 'Frame/sample and encoder timebases determine actual output; no millisecond-exact promise.',
                                   'autorotate': 'ffmpeg-default', 'crop': False, 'scale': False}}
            write_record(record_path, record)
        source = local_source(args.source) if args.operation != 'doctor' else None
        if source:
            evidence = {'name': source.name, 'canonicalPath': str(source),
                        'sha256': digest(source), 'bytes': source.stat().st_size}
            if record:
                record['source'] = evidence
        ffprobe = find_tool('ffprobe', args.ffprobe, project)
        probe_details = tool_details(ffprobe)
        if record:
            record['tools']['ffprobe'] = probe_details
        if args.operation != 'doctor':
            metadata = probe_media(ffprobe, source)
            if args.operation == 'probe':
                return {'ok': True, 'operation': 'probe', 'source': evidence, 'metadata': metadata,
                        'tools': {'ffprobe': probe_details}, 'visualReview': 'not-reviewed'}
            record['source']['metadata'] = metadata
            bounded_request(request, metadata)
            video, audio = select_streams(metadata, request)
            record['strategy']['videoStreamIndex'] = video['index'] if video else None
            record['strategy']['audioStreamIndex'] = audio['index'] if audio else None
        ffmpeg = find_tool('ffmpeg', args.ffmpeg, project)
        ffmpeg_details = tool_details(ffmpeg)
        encoders, muxers = capabilities(ffmpeg)
        if args.operation == 'doctor':
            operations = {name: capability_result(name, encoders, muxers) for name in ('probe', 'clip', 'audio', 'frames')}
            return {'ok': True, 'operation': 'doctor', 'tools': {'ffmpeg': ffmpeg_details, 'ffprobe': probe_details},
                    'operations': operations, 'encoders': sorted(encoders), 'muxers': sorted(muxers),
                    'note': 'Capabilities cover required encoders and muxers; source-specific decoding support is checked during processing.'}
        record['tools']['ffmpeg'] = ffmpeg_details
        capability = capability_result(args.operation, encoders, muxers, bool(audio))
        if not capability['available']:
            raise MediaError('unsupported_operation', 'This FFmpeg build lacks: ' + ', '.join(capability['missing']))
        derived = safe_folder(project, 'public/derived')
        destination = derived / record['id']
        if destination.exists() or destination.is_symlink():
            raise MediaError('output_exists', 'A destination with this job ID already exists; nothing was overwritten.')
        staging = record_path.parent / '.staging'
        staging.mkdir(exist_ok=False)
        files = extract(ffmpeg, source, request, video, audio, staging)
        outputs = []
        for file in files:
            outputs.append({'file': 'derived/' + record['id'] + '/' + file.name,
                            'sha256': digest(file) if file.is_file() else None,
                            'metadata': validate_output(file, args.operation, ffprobe, ffmpeg)})
        if digest(source) != evidence['sha256']:
            raise MediaError('source_changed', 'Source changed during processing; outputs were not adopted.')
        if destination.exists() or destination.is_symlink():
            raise MediaError('output_exists', 'Destination appeared while processing; nothing was overwritten.')
        staging.rename(destination)
        published = True
        record.update({'status': 'completed', 'completedAt': timestamp(), 'outputs': outputs})
        write_record(record_path, record)
        return {'ok': True, 'operation': args.operation, 'id': record['id'],
                'record': record_path.relative_to(project).as_posix(), 'outputs': outputs,
                'visualReview': 'not-reviewed'}
    except (MediaError, OSError) as error:
        if isinstance(error, MediaError):
            diagnostic = {'code': error.code, 'message': str(error)}
        else:
            diagnostic = {'code': 'output_unavailable', 'message': str(error)}
        if staging and staging.exists():
            shutil.rmtree(staging)
        if published and destination and destination.exists():
            shutil.rmtree(destination)
        result = {'ok': False, 'operation': args.operation, 'error': diagnostic}
        if record and record_path:
            record.update({'status': 'failed', 'completedAt': timestamp(), 'outputs': [], 'error': diagnostic})
            try:
                write_record(record_path, record)
                result['record'] = record_path.relative_to(project).as_posix()
            except OSError as save_error:
                result['recordError'] = 'Could not persist failure record: ' + str(save_error)
        return result


def main(argv=None):
    try:
        result = execute(parser().parse_args(argv))
    except MediaError as error:
        result = {'ok': False, 'error': {'code': error.code, 'message': str(error)}}
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())

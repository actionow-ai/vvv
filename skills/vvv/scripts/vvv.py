#!/usr/bin/env python3
"""Local VVV helper. Use --help for the supported operations."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import traceback

# The range scripts/render.mjs accepts for --scale.
MAX_SCALE = 2.0
FAILED_CODES = {'validate': 'VALIDATION_FAILED', 'inspect': 'VALIDATION_FAILED', 'sample': 'VALIDATION_FAILED',
                'render': 'VALIDATION_FAILED', 'check': 'CHECK_FAILED', 'evidence': 'CHECK_FAILED',
                'verify': 'PACKAGE_INVALID'}


class JSONParser(argparse.ArgumentParser):
    """Argument errors are failures like any other: one JSON object on stdout."""
    def error(self, message):
        emit({'status': 'failed', 'code': 'INVALID_ARGUMENTS', 'message': f'{self.prog}: {message}',
              'next': run(sys.executable, SCRIPT, *self.prog.split()[1:], '--help')})
        raise SystemExit(2)


def emit(result):
    """One JSON object, a key per line with compact values (lists of objects: an item per line), to save tokens."""
    def compact(value):
        return json.dumps(value, ensure_ascii=False, separators=(', ', ': '))
    lines = []
    for key, value in result.items():
        if isinstance(value, list) and value and all(isinstance(v, dict) for v in value):
            lines.append(f'  {compact(key)}: [\n' + ',\n'.join('    ' + compact(v) for v in value) + '\n  ]')
        else:
            lines.append(f'  {compact(key)}: {compact(value)}')
    print('{\n' + ',\n'.join(lines) + '\n}' if lines else '{}')


def failure(error):
    """{"status": "failed", "code", "message"} from an exception; messages may start with "CODE: "."""
    text = str(error.args[0]) if isinstance(error, KeyError) and error.args else str(error)
    if type(error).__name__ == 'MediaError':
        return {'status': 'failed', 'code': str(error.code).upper(), 'message': text}
    match = re.match(r'([A-Z][A-Z0-9_]+): (.*)', text, re.DOTALL)
    if match:
        return {'status': 'failed', 'code': match.group(1), 'message': match.group(2)}
    if isinstance(error, json.JSONDecodeError):
        code = 'INVALID_JSON'
    elif isinstance(error, OSError):
        code, text = 'FILE_ERROR', f'{error.strerror or error}: {error.filename}' if error.filename else text
    elif isinstance(error, KeyError):
        code, text = 'INVALID_DATA', f'Missing field {text!r}.'
    elif isinstance(error, TypeError):
        code = 'INVALID_DATA'
    else:
        code = 'INVALID_INPUT'
    return {'status': 'failed', 'code': code, 'message': text}


def summarize(command, result):
    """A failed report keeps its details and leads with a code and message like every other failure."""
    if result.get('status') != 'failed' or 'code' in result:
        return result
    checks = result.get('checks') or (result.get('validation') or {}).get('checks') or []
    failed = [c for c in checks if c.get('status') == 'failed']
    message = '; '.join(f"{c.get('code')}: {c.get('message')}" for c in failed[:3]) + (' …' if len(failed) > 3 else '')
    return {'status': 'failed', 'code': FAILED_CODES.get(command, 'FAILED'),
            'message': message or 'See the report.', **{k: v for k, v in result.items() if k != 'status'}}


def default_kit():
    """The kit when --kit is omitted: $VVV_KIT, else the kit bundled beside this skill (a clone or an installed plugin)."""
    if os.environ.get('VVV_KIT'):
        return Path(os.environ['VVV_KIT'])
    bundled = Path(__file__).resolve().parents[3] / 'kits' / 'remotion'
    return bundled if (bundled / 'catalog').is_dir() else None


KIT_HINT = ('Pass --kit, or set VVV_KIT to the kit directory (kits/remotion in a clone of '
            'https://github.com/actionow-ai/vvv); the Claude Code plugin bundles it.')
SCRIPT = str(Path(__file__).resolve())
REQUIREMENTS = str(Path(__file__).resolve().parents[1] / 'requirements.txt')


def run(*command, cwd=None, then=None):
    """A next step the agent runs itself."""
    step = {'action': 'run', 'command': list(command)}
    if cwd:
        step['cwd'] = str(cwd)
    if then:
        step['then'] = then
    return step


def ask_user(say):
    """A next step only the user can take (permission, a system install, missing material); say it in one sentence."""
    return {'action': 'ask_user', 'say': say}


def fix(hint):
    """A next step the agent works out itself from the message (inputs, source or a new path)."""
    return {'action': 'fix', 'hint': hint}


def next_step(code, args):
    """What the agent does after a failure, so it recovers without relaying the error to the user."""
    project = getattr(args, 'project', None)
    project = Path(project).expanduser().resolve() if project and not str(project).endswith('.vvv') else None
    command = getattr(args, 'command', None)
    steps = {
        'DEPENDENCY_MISSING': run(sys.executable, '-m', 'pip', 'install', '-r', REQUIREMENTS,
                                  then='If pip refuses (an externally managed Python), create a virtual environment '
                                       'and use its python for every vvv.py command.'),
        'KIT_REQUIRED': run(sys.executable, SCRIPT, 'doctor'),
        'KIT_NOT_FOUND': run(sys.executable, SCRIPT, 'doctor'),
        'NODE_MISSING': ask_user('Rendering needs Node.js 22 or newer on this computer. May I install it?'),
        'DEPENDENCIES_MISSING': run('npm', 'ci', cwd=project, then=f'Rerun {command}.') if project else None,
        'DOWNLOAD_PENDING': run('npm', 'run', 'music', cwd=project, then=f'Rerun {command}.') if project else None,
        'UNKNOWN_TEMPLATE': run(sys.executable, SCRIPT, 'templates'),
        'UNSUPPORTED_FORMAT': fix('Run describe for the template to see its formats; pick one or another template.'),
        'INSUFFICIENT_PHOTOS': fix('Ask the user for more photos, choose a template whose minPhotos fits, '
                                   'or pass --allow-repeat if repeating photos is acceptable.'),
        'NO_USABLE_PHOTOS': ask_user('None of these files are usable photos. Could you send the photos as JPG, PNG or HEIC?'),
        'PHOTOS_REQUIRED': fix('Pass --photos with the user\'s photos, or --example for a demo render.'),
        'VALIDATION_FAILED': fix('Fix each failed check (inputs.json, photos or music), then run validate again.'),
        'CHECK_FAILED': fix('Fix the failed checks in the source or inputs (see references/craft.md), '
                            're-render the affected range and check again.'),
        'DESTINATION_EXISTS': fix('Choose a new output path; never overwrite an existing file.'),
        'INVALID_ARGUMENTS': run(sys.executable, SCRIPT, *([command] if command else []), '--help'),
        'TOOL_MISSING': (run('npm', 'ci', cwd=project, then='Rerun the command.') if project else
                         fix('Run the command with --project, or pass --ffmpeg and --ffprobe.')),
        'PACKAGE_INVALID': ask_user('This .vvv package failed verification, so I will not use it. Do you have another copy?'),
        'TAGS_MISSING': fix('Look at creative/contact-sheet.jpg (or the photos), write creative/photo-tags.json '
                            '(see references/story-editing.md) and run arrange again.'),
        'TAGS_INVALID': fix('Correct creative/photo-tags.json as the message says and run arrange again.'),
        'ARRANGE_INVALID': fix('The arranged photos do not validate; fix the tags (pins, skips) or pass --allow-repeat.'),
        'STYLE_NOT_FOUND': run(sys.executable, SCRIPT, 'style', 'list'),
        'STYLE_INVALID': fix('Fix the preset\'s style.json, or apply only the parts that fit this template.'),
        'INTERNAL_ERROR': fix('Rerun with VVV_DEBUG=1 for a traceback; if it persists, report it at '
                              'https://github.com/actionow-ai/vvv/issues.'),
    }
    return steps.get(code)


def with_next(result, args):
    """Attach the next step to a failure that does not carry one."""
    if result.get('status') == 'failed' and 'next' not in result:
        step = next_step(result.get('code'), args)
        if step:
            result = {**result, 'next': step}
    return result


def positive(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError('Expected a positive finite number.')
    return number


def scale(value):
    number = positive(value)
    if number > MAX_SCALE:
        raise argparse.ArgumentTypeError(f'Expected a scale above 0 and at most {MAX_SCALE:g}.')
    return number


def nonnegative(value):
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError('Expected a nonnegative finite number.')
    return number


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')  # CJK output when piped on Windows code pages
        except (OSError, ValueError):
            pass
    parser = JSONParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    doctor = commands.add_parser('doctor', help='Check what rendering needs; every gap comes with its fix. Run it first.')
    doctor.add_argument('--kit', type=Path, help='The kit directory; defaults to $VVV_KIT or the bundled kits/remotion.')
    doctor.add_argument('--project', type=Path, help='Also check a project: dependencies, downloads and inputs.')
    templates = commands.add_parser('templates', help='List the templates and formats a kit provides.')
    templates.add_argument('--kit', type=Path, help='The kit directory; defaults to $VVV_KIT or the bundled kits/remotion.')
    describe = commands.add_parser('describe', help='Everything needed to fill one template\'s inputs, as one record.')
    describe.add_argument('--kit', type=Path, help='The kit directory; not needed when --template is a .vvv file.')
    describe.add_argument('--template', required=True, help='A template ID from the kit, or a template package file (.vvv).')
    describe.add_argument('--format', dest='frame_format', help='Frame format to describe slots for; defaults to the template default.')
    effects = commands.add_parser('effects', help='List the effects a kit provides.')
    effects.add_argument('--kit', type=Path, help='The kit directory; defaults to $VVV_KIT or the bundled kits/remotion.')
    add = commands.add_parser('add', help='Add an effect package (.vvv) to a project.')
    add.add_argument('--project', required=True, type=Path)
    add.add_argument('--effect', required=True, type=Path)
    init = commands.add_parser('init', help='Create an editable project from local still images.')
    init.add_argument('--kit', type=Path, help='The kit directory; not needed when --template is a .vvv file.')
    init.add_argument('--template', required=True, help='A template ID from the kit, or a template package file (.vvv).')
    init.add_argument('--format', dest='frame_format', help='Frame format such as 16:9 or 9:16; defaults to the template default.')
    source = init.add_mutually_exclusive_group()
    source.add_argument('--photos', action='append', type=Path, default=[],
                        help='Photo directory or file (repeatable); not needed for templates without photo slots.')
    source.add_argument('--example', action='store_true',
                        help='Use the template\'s shipped demo photos and copy: a correctly mapped first render.')
    init.add_argument('--output', required=True, type=Path)
    init.add_argument('--allow-repeat', action='store_true')
    init.add_argument('--style', help='A saved style preset (name or path) to apply to the new project.')
    init.add_argument('--max-size', dest='max_size', type=int, help='Long side of the project copies in px (default 2560; 0 keeps originals).')
    init.add_argument('--faces', action='store_true', help='Detect faces for cropping (needs OpenCV; never installed for you).')
    arrange = commands.add_parser('arrange', help='Place the photos along the template\'s emotional arc from creative/photo-tags.json.')
    arrange.add_argument('--project', required=True, type=Path)
    arrange.add_argument('--allow-repeat', action='store_true')
    update = commands.add_parser('update', help='Bring a project\'s template code up to date with the kit; edited files are conflicts.')
    update.add_argument('--project', required=True, type=Path)
    update.add_argument('--kit', type=Path, help='The kit directory; defaults to $VVV_KIT or the bundled kits/remotion.')
    update.add_argument('--apply', action='store_true', help='Write the updates (default: report only).')
    update.add_argument('--take-kit', dest='take_kit', action='store_true', help='Also overwrite files edited in the project.')
    music = commands.add_parser('music', help='Add the user\'s track to a project, and fit a song to the template.')
    musics = music.add_subparsers(dest='music_command', required=True)
    music_add = musics.add_parser('add', help='Copy a local audio file in, measure its beats, record it and use it.')
    music_add.add_argument('--project', required=True, type=Path)
    music_add.add_argument('--file', required=True, type=Path)
    music_add.add_argument('--name', help='File name in public/music (default: from the file).')
    music_add.add_argument('--keep-inputs', action='store_true', help='Record the track without switching inputs.json to it.')
    music_fit = musics.add_parser('fit', help='Choose where the song starts and the pace so the chorus opens the climax page.')
    music_fit.add_argument('--project', required=True, type=Path)
    music_fit.add_argument('--climax', help='Page that should open on the chorus (default: the template\'s climax page).')
    music_fit.add_argument('--seconds', type=positive, help='Target film length; default: the shortest holds of about 5 s.')
    music_fit.add_argument('--apply', action='store_true', help='Write trimBeforeSec and the pace to inputs.json.')
    style = commands.add_parser('style', help='Save, list and apply style presets that carry settled choices across films.')
    styles = style.add_subparsers(dest='style_command', required=True)
    styles.add_parser('list', help='Saved presets.')
    style_save = styles.add_parser('save', help='Save an approved project\'s choices as a preset.')
    style_save.add_argument('--project', required=True, type=Path)
    style_save.add_argument('--name', required=True)
    style_save.add_argument('--keep', action='append', default=[], help='A props path to keep, e.g. copy.thanks (repeatable).')
    style_save.add_argument('--constraint', action='append', default=[], help='A rule for every film (repeatable).')
    style_save.add_argument('--description')
    style_save.add_argument('--replace', action='store_true', help='Update an existing preset of that name.')
    style_apply = styles.add_parser('apply', help='Apply a preset to a project.')
    style_apply.add_argument('--project', required=True, type=Path)
    style_apply.add_argument('--style', required=True, help='Preset name or path.')
    check = commands.add_parser('check', help='Measure a rendered video: format, sound, still holds and beat sync.')
    check.add_argument('--project', type=Path, help='Use the project format, limits and beat map.')
    check.add_argument('--video', type=Path, help='Defaults to the most recent sample or render report output.')
    check.add_argument('--beats', type=Path, help='Without --project: a beat map to compare cuts with.')
    check.add_argument('--max-still', type=positive, default=3.0, help='Without --project: longest allowed still stretch.')
    check.add_argument('--ffmpeg')
    check.add_argument('--ffprobe')
    pack = commands.add_parser('pack', help='Write a .vvv package: a template or effect from a kit, or a project.')
    pack.add_argument('--kit', type=Path)
    pack.add_argument('--template', help='Template ID in the kit.')
    pack.add_argument('--effect', help='Effect ID in the kit.')
    pack.add_argument('--project', type=Path, help='Package a project to hand over or continue elsewhere.')
    pack.add_argument('--output', required=True, type=Path, help='Destination file ending in .vvv; must not exist.')
    pack.add_argument('--preview', type=Path, help='Template/effect: a short MP4 preview to include.')
    pack.add_argument('--poster', type=Path, help='Template/effect: a JPEG poster to include.')
    pack.add_argument('--evidence', type=Path, action='append', default=[],
                      help='Template/effect: a check record from the evidence command (repeatable).')
    pack.add_argument('--strip-media', action='store_true', help='Project: leave out the owner\'s photos and contact sheets.')
    verify = commands.add_parser('verify', help='Check a .vvv package without extracting or running it.')
    verify.add_argument('--package', required=True, type=Path)
    unpack = commands.add_parser('unpack', help='Verify and extract a .vvv package into a new directory.')
    unpack.add_argument('--package', required=True, type=Path)
    unpack.add_argument('--output', required=True, type=Path)
    evidence = commands.add_parser('evidence', help='Check the latest render and tie the result to the files it measured.')
    evidence.add_argument('--project', required=True, type=Path)
    evidence.add_argument('--video', type=Path)
    evidence.add_argument('--output', required=True, type=Path, help='JSON file to write, e.g. check-16x9.json.')
    evidence.add_argument('--ffmpeg')
    evidence.add_argument('--ffprobe')
    inspect = commands.add_parser('inspect', help='Read a project, or a package manifest without running it.')
    inspect.add_argument('--project', type=Path)
    inspect.add_argument('--package', type=Path)
    inspect.add_argument('--verbose', action='store_true', help='List passed checks too.')
    for command in ['validate', 'sample', 'render']:
        sub = commands.add_parser(command)
        sub.add_argument('--project', required=True, type=Path)
        if command == 'validate':
            sub.add_argument('--verbose', action='store_true', help='List passed checks too.')
        if command in {'sample', 'render'}:
            sub.add_argument('--scale', type=scale, default=0.5, help=f'Above 0 and at most {MAX_SCALE:g}; 1 is native size.')
        if command == 'sample':
            sub.add_argument('--from', dest='start', type=nonnegative)
            sub.add_argument('--to', dest='end', type=positive)
    args = parser.parse_args(argv)
    if args.command == 'doctor':
        # Before the other imports: it must work when Pillow is missing.
        from vvv_doctor import doctor as check_environment
        result = check_environment(args.kit or default_kit(), args.project, run, ask_user, fix, SCRIPT, REQUIREMENTS)
        emit(result)
        return 1 if result['status'] == 'failed' else 0
    try:
        # Imported after parsing so --help works before the dependencies are installed.
        from vvv_project import create_project, describe_template, inspect_project, list_templates, validate_project
        if hasattr(args, 'kit') and args.kit is None:
            args.kit = default_kit()
        needs_kit = args.command in ('templates', 'effects') or (
            args.command in ('describe', 'init') and not args.template.endswith('.vvv')) or (
            args.command == 'pack' and not args.project)
        if needs_kit and args.kit is None:
            raise ValueError('KIT_REQUIRED: ' + KIT_HINT)
        if args.command == 'templates':
            result = {'status': 'passed', 'templates': list_templates(args.kit)}
        elif args.command == 'describe':
            result = describe_template(args.kit, args.template, args.frame_format,
                                       sys.argv[0] if argv is None and sys.argv[0].endswith('.py') else 'scripts/vvv.py')
        elif args.command == 'effects':
            result = {'status': 'passed', 'effects': list_templates(args.kit, 'effect')}
        elif args.command == 'add':
            import vvv_package
            result = vvv_package.add_effect(args.project, args.effect)
        elif args.command == 'init':
            import vvv_style
            preset = vvv_style.resolve(args.style) if args.style else None  # fail before creating anything
            result = create_project(args.kit, args.template, args.photos, args.output, args.allow_repeat,
                                    args.frame_format, args.example, args.max_size, args.faces)
            if preset:
                try:
                    result['style'] = vvv_style.apply(result['project'], preset)
                except BaseException:
                    shutil.rmtree(result['project'], ignore_errors=True)
                    raise
        elif args.command == 'arrange':
            from vvv_arc import arrange as arrange_photos
            result = arrange_photos(args.project, args.allow_repeat)
        elif args.command == 'update':
            from vvv_project import update_project
            if args.kit is None:
                raise ValueError('KIT_REQUIRED: ' + KIT_HINT)
            result = update_project(args.project, args.kit, args.apply, args.take_kit)
        elif args.command == 'music':
            import vvv_music
            if args.music_command == 'add':
                result = vvv_music.add(args.project, args.file, args.name, not args.keep_inputs)
            else:
                result = vvv_music.fit(args.project, args.climax, args.seconds, args.apply)
        elif args.command == 'style':
            import vvv_style
            if args.style_command == 'list':
                result = {'status': 'passed', 'directory': str(vvv_style.styles_dir()), 'styles': vvv_style.list_styles()}
            elif args.style_command == 'save':
                result = vvv_style.save(args.project, args.name, args.keep, args.constraint, args.description, args.replace)
            else:
                result = vvv_style.apply(args.project, args.style)
        elif args.command == 'pack':
            import vvv_package
            chosen = [x for x in (args.template, args.effect, args.project) if x]
            if len(chosen) != 1:
                raise ValueError('PACK_TARGET: Pass exactly one of --template, --effect or --project.')
            if args.project:
                result = vvv_package.pack_project(args.project, args.output, args.strip_media)
            else:
                result = vvv_package.pack_template(args.kit, args.template or args.effect, args.output, args.preview,
                                                   args.poster, args.evidence, 'template' if args.template else 'effect')
        elif args.command == 'verify':
            import vvv_package
            result = vvv_package.verify_package(args.package)
        elif args.command == 'unpack':
            import vvv_package
            result = vvv_package.unpack(args.package, args.output)
        elif args.command == 'evidence':
            import vvv_package
            from vvv_check import check_project, latest_output
            from vvv_project import write_json
            project = args.project.expanduser().resolve()
            if args.output.exists() or args.output.is_symlink():
                raise ValueError(f'DESTINATION_EXISTS: {args.output.name}')
            checked = check_project(project, args.video, args.ffmpeg, args.ffprobe)
            if 'validation' in checked:
                result = checked
            else:
                report = None if args.video else latest_output(project)
                record = vvv_package.evidence_record(project, checked, report)
                if args.output.exists():
                    raise ValueError(f'DESTINATION_EXISTS: {args.output.name}')
                write_json(args.output, record)
                result = {'status': checked['status'], 'output': str(args.output), 'fingerprint': record['fingerprint'],
                          **({'checks': [c for c in checked['checks'] if c['status'] == 'failed']}
                             if checked['status'] == 'failed' else {})}
        elif args.command == 'check':
            from vvv_check import check_file, check_project
            if args.project:
                result = check_project(args.project, args.video, args.ffmpeg, args.ffprobe)
            elif args.video:
                result = check_file(args.video, args.beats, args.max_still, args.ffmpeg, args.ffprobe)
            else:
                raise ValueError('CHECK_TARGET: Pass --project, or --video to measure any file such as a reference.')
        elif args.command == 'inspect':
            if bool(args.project) == bool(args.package):
                raise ValueError('INSPECT_TARGET: Pass --project or --package.')
            if args.package:
                import vvv_package
                result = vvv_package.inspect_package(args.package)
            else:
                result = inspect_project(args.project, args.verbose)
        elif args.command == 'validate':
            result = validate_project(args.project, args.verbose)
        else:
            project = args.project.expanduser().resolve()
            validation = validate_project(project)
            if validation['status'] != 'passed':
                if validation['status'] == 'pending':
                    validation = {'status': 'failed', 'code': 'DOWNLOAD_PENDING',
                                  'message': 'Run npm run music in the project first: '
                                             + '; '.join(c['message'] for c in validation['checks'] if c['status'] == 'pending'),
                                  **{k: v for k, v in validation.items() if k != 'status'}}
                emit(with_next(summarize(args.command, validation), args))
                return 1
            node = shutil.which('node')
            if not node:
                raise ValueError('NODE_MISSING: Install Node.js to render this project.')
            if not (project / 'node_modules' / '@remotion' / 'renderer').is_dir():
                raise ValueError('DEPENDENCIES_MISSING: Run npm ci inside the project first.')
            # Reuse a Chrome Headless Shell this computer already has instead of downloading it per project.
            from vvv_doctor import cache_chrome, provide_chrome
            provide_chrome(project, default_kit())
            command = [node, str(project / 'scripts' / 'render.mjs'), '--project', str(project),
                       '--mode', args.command, '--scale', str(args.scale)]
            if args.command == 'sample':
                if args.start is not None:
                    command += ['--from', str(args.start)]
                if args.end is not None:
                    command += ['--to', str(args.end)]
            code = subprocess.run(command, cwd=project, check=False).returncode
            if code == 0:
                cache_chrome(project)
            return code
        emit(with_next(summarize(args.command, result), args))
        return 1 if result.get('status') == 'failed' else 0
    except ModuleNotFoundError as error:
        if error.name != 'PIL':
            return internal(error, args)
        emit(with_next({'status': 'failed', 'code': 'DEPENDENCY_MISSING',
                        'message': f'Pillow is not installed for {sys.executable}.'}, args))
        return 1
    except (OSError, ValueError, KeyError, TypeError) as error:
        emit(with_next(failure(error), args))
        return 1
    except Exception as error:  # MediaError from the check command carries a machine-readable code.
        if type(error).__name__ != 'MediaError':
            return internal(error, args)
        emit(with_next(failure(error), args))
        return 1


def internal(error, args=None):
    if os.environ.get('VVV_DEBUG') == '1':
        traceback.print_exc()
    emit(with_next({'status': 'failed', 'code': 'INTERNAL_ERROR',
                    'message': f'{type(error).__name__}: {error}. Rerun with VVV_DEBUG=1 for a traceback.'}, args))
    return 1


if __name__ == '__main__':
    raise SystemExit(main())

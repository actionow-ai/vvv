"""Style presets: settle a studio's or couple's choices once and apply them to every new project.

A preset is a directory with style.json (and, for the user's own soundtrack, the track and its beat map):

    {"vvvStyle": "1", "name": "harbor-studio", "description": "...",
     "constraints": ["Open on both faces within the first 3 seconds.", "Names in Chinese, then English."],
     "music": {"mood": "warm piano, slow build", "src": "music/mixkit-skyline.mp3", "volume": 0.8,
               "fadeInSec": 0.3, "fadeOutSec": 2.5},
     "arc": {"opening": {"mood": ["romantic"], "subject": ["couple"]}},
     "templates": {"album": {"props": {"copy": {"gallery_title": "..."}}}}}

`music.file` (instead of `src`) names a track inside the preset directory. Constraints are the agent's rules
and land in vvv.json `workflow.approvedConstraints`; `arc` steers `arrange`; `templates.<id>.props` merge into
inputs.json. Presets live in $VVV_STYLES or ~/.vvv/styles/<name>/.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from vvv_project import MOODS, SUBJECTS, download_records, load_catalog, read_json, validate_project, write_json

NAME = re.compile(r'[a-z0-9][a-z0-9-]{0,47}')
MUSIC_KEYS = ('volume', 'fadeInSec', 'fadeOutSec', 'trimBeforeSec')
NOT_STYLE = ('photos', 'copy', 'couple', 'music', 'fps', 'format')  # per-film props; copy and couple only via --keep
FILE = 'style.json'


def styles_dir():
    return Path(os.environ.get('VVV_STYLES') or Path.home() / '.vvv' / 'styles').expanduser()


def resolve(style):
    """A preset name under styles_dir(), or a path to a preset directory or its style.json."""
    path = Path(style).expanduser()
    if path.is_dir() and (path / FILE).is_file():
        return path / FILE
    if path.name == FILE and path.is_file():
        return path
    if NAME.fullmatch(str(style)) and (styles_dir() / str(style) / FILE).is_file():
        return styles_dir() / str(style) / FILE
    names = [s['name'] for s in list_styles()]
    raise ValueError(f'STYLE_NOT_FOUND: {style}; saved presets: {", ".join(names) or "none"}.')


def load(path):
    try:
        document = read_json(path)
    except (OSError, ValueError) as error:
        raise ValueError(f'STYLE_INVALID: {path.name}: {error}') from None
    problems = []
    if not isinstance(document, dict) or document.get('vvvStyle') != '1':
        raise ValueError('STYLE_INVALID: expected {"vvvStyle": "1", ...}.')
    if not NAME.fullmatch(str(document.get('name', ''))):
        problems.append('name must be lowercase letters, digits and hyphens')
    if not isinstance(document.get('constraints', []), list) or not all(isinstance(c, str) for c in document.get('constraints', [])):
        problems.append('constraints must be a list of strings')
    music = document.get('music', {})
    if not isinstance(music, dict) or ('src' in music and 'file' in music):
        problems.append('music must be an object with src or file, not both')
    elif not all(isinstance(music[k], (int, float)) and not isinstance(music[k], bool) for k in MUSIC_KEYS if k in music):
        problems.append('music volume and fade values must be numbers')
    elif 'file' in music and (not isinstance(music['file'], str) or Path(music['file']).is_absolute()
                              or '..' in Path(music['file']).parts):
        problems.append('music.file must be a path inside the preset directory')
    arc = document.get('arc', {})
    if not isinstance(arc, dict) or not all(
            isinstance(v, dict) and all(m in MOODS for m in v.get('mood', [])) and all(s in SUBJECTS for s in v.get('subject', []))
            for v in arc.values()):
        problems.append(f'arc maps section ids to {{"mood": [{", ".join(MOODS)}], "subject": [...]}}')
    templates = document.get('templates', {})
    if not isinstance(templates, dict) or not all(isinstance(v, dict) and isinstance(v.get('props', {}), dict)
                                                  for v in templates.values()):
        problems.append('templates maps template ids to {"props": {...}}')
    if problems:
        raise ValueError('STYLE_INVALID: ' + '; '.join(problems))
    return document


def list_styles():
    root, found = styles_dir(), []
    for path in sorted(root.glob(f'*/{FILE}')) if root.is_dir() else []:
        try:
            document = load(path)
        except ValueError as error:
            found.append({'name': path.parent.name, 'status': 'invalid', 'message': str(error)})
            continue
        found.append({'name': document['name'], 'description': document.get('description', ''),
                      'templates': sorted(document.get('templates', {})), 'constraints': len(document.get('constraints', [])),
                      **({'music': document['music'].get('mood') or document['music'].get('src') or document['music'].get('file')}
                         if document.get('music') else {})})
    return found


def merge(base, extra):
    """Objects merge key by key; anything else from `extra` replaces."""
    result = deepcopy(base)
    for key, value in extra.items():
        result[key] = merge(result[key], value) if isinstance(value, dict) and isinstance(result.get(key), dict) else deepcopy(value)
    return result


def dotted(props, path):
    value = props
    for part in path.split('.'):
        if not isinstance(value, dict) or part not in value:
            raise ValueError(f'STYLE_KEEP: props.{path} does not exist in this project.')
        value = value[part]
    nested = deepcopy(value)
    for part in reversed(path.split('.')):
        nested = {part: nested}
    return nested


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(project, name, keep=(), constraints=(), description=None, replace=False):
    """Write a preset from an approved project: its template options, the --keep props, its music, its approved
    constraints and the arc preferences of a style already applied to it."""
    project = Path(project).expanduser().resolve()
    if not NAME.fullmatch(name or ''):
        raise ValueError('STYLE_NAME: Use lowercase letters, digits and hyphens, e.g. harbor-studio.')
    inputs = read_json(project / 'inputs.json')
    template, props = inputs.get('template'), inputs.get('props') or {}
    catalog = load_catalog(project, template)
    defaults = catalog['defaultProps']
    options = {k: deepcopy(v) for k, v in props.items() if k not in NOT_STYLE and v != defaults.get(k)}
    for path in keep:
        options = merge(options, dotted(props, path))
    manifest = read_json(project / 'vvv.json') if (project / 'vvv.json').is_file() else {}
    approved = [c for c in (manifest.get('workflow') or {}).get('approvedConstraints', []) if isinstance(c, str)]
    applied = read_json(project / 'creative' / 'style.json') if (project / 'creative' / 'style.json').is_file() else {}

    destination = styles_dir() / name
    if destination.exists() and not replace:
        raise ValueError(f'DESTINATION_EXISTS: preset {name} exists; pass --replace to update it.')
    previous = load(destination / FILE) if (destination / FILE).is_file() else {}
    music, track = {k: props['music'][k] for k in MUSIC_KEYS if k in (props.get('music') or {})}, None
    src = (props.get('music') or {}).get('src')
    if src:
        kit_tracks = {f"{r.get('dir', 'music')}/{r.get('file')}" for r in read_json_or(project / 'public' / 'music' / 'sources.json').get('tracks', [])
                      if isinstance(r, dict)}
        if src in kit_tracks:
            music['src'] = src  # every project from the kit has or fetches it
        else:
            track = project / 'public' / src
            if not track.is_file():
                raise ValueError(f'STYLE_MUSIC: {src} is not in the project; fetch or add it first.')
            music['file'] = 'music/' + track.name
    for key in ('mood',):
        if (previous.get('music') or {}).get(key):
            music[key] = previous['music'][key]
    document = {'vvvStyle': '1', 'name': name,
                'description': description if description is not None else previous.get('description', ''),
                'constraints': list(dict.fromkeys([*previous.get('constraints', []), *approved, *constraints])),
                **({'music': music} if music else {}),
                **({'arc': merge(previous.get('arc', {}), applied.get('arc', {}))} if previous.get('arc') or applied.get('arc') else {}),
                'templates': {**previous.get('templates', {}), template: {'props': options}}}

    styles_dir().mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f'.{name}-', dir=styles_dir()))
    try:
        if destination.is_dir():
            shutil.copytree(destination, staging, dirs_exist_ok=True)
        if track:
            (staging / 'music').mkdir(exist_ok=True)
            shutil.copy2(track, staging / 'music' / track.name)
            beats = track.with_name(track.name.rsplit('.', 1)[0] + '.beats.json')
            if beats.is_file():
                shutil.copy2(beats, staging / 'music' / beats.name)
        write_json(staging / FILE, document)
        load(staging / FILE)
        if destination.exists():
            shutil.rmtree(destination)
        staging.rename(destination)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {'status': 'saved', 'style': name, 'path': str(destination / FILE), 'template': template,
            'props': sorted(flatten(options)), 'constraints': len(document['constraints']),
            **({'music': music.get('src') or music.get('file')} if music else {}),
            'next': {'action': 'fix', 'hint': 'Tell the user the preset name; use init --style or style apply on the next film.'}}


def read_json_or(path):
    try:
        return read_json(path)
    except (OSError, ValueError):
        return {}


def flatten(value, prefix=''):
    if isinstance(value, dict) and value:
        return [p for k, v in value.items() for p in flatten(v, f'{prefix}{k}.')]
    return [prefix.rstrip('.')]


def apply(project, style):
    """Merge a preset into a project; nothing is changed when the result does not validate."""
    project = Path(project).expanduser().resolve()
    path = resolve(style)
    document = load(path)
    inputs = read_json(project / 'inputs.json')
    template, props = inputs.get('template'), inputs.get('props') or {}
    manifest = read_json(project / 'vvv.json')
    backups = {p: p.read_bytes() for p in (project / 'inputs.json', project / 'vvv.json', project / 'creative' / 'style.json')
               if p.is_file()}
    created = []
    try:
        extra = (document.get('templates', {}).get(template) or {}).get('props', {})
        props = merge(props, extra)
        music = dict(props.get('music') or {})
        style_music = document.get('music') or {}
        music.update({k: style_music[k] for k in MUSIC_KEYS if k in style_music})
        if style_music.get('src'):
            music['src'] = style_music['src']
        if style_music.get('file'):
            source = path.parent / style_music['file']
            if not source.is_file():
                raise ValueError(f'STYLE_MUSIC: {style_music["file"]} is missing from preset {document["name"]}.')
            for item in [source, source.with_name(source.name.rsplit('.', 1)[0] + '.beats.json')]:
                if not item.is_file():
                    continue
                target = project / 'public' / 'music' / item.name
                if target.exists() and digest(target) != digest(item):
                    raise ValueError(f'STYLE_CONFLICT: public/music/{item.name} already exists with different content.')
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, target)
                    created.append(target)
            music['src'] = 'music/' + source.name
        if music:
            props['music'] = music
        write_json(project / 'inputs.json', {**inputs, 'props': props})
        workflow = dict(manifest.get('workflow') or {})
        approved = list(workflow.get('approvedConstraints') or [])
        added = [c for c in document.get('constraints', []) if c not in approved]
        workflow['approvedConstraints'] = approved + added
        workflow['style'] = {'name': document['name'], 'sha256': digest(path)}
        write_json(project / 'vvv.json', {**manifest, 'workflow': workflow})
        (project / 'creative').mkdir(exist_ok=True)
        write_json(project / 'creative' / 'style.json', document)
        validation = validate_project(project)
        if validation['status'] == 'failed':
            raise ValueError('STYLE_INVALID: the preset does not fit this project: ' + '; '.join(
                c['code'] + ': ' + c['message'] for c in validation['checks'] if c['status'] == 'failed'))
    except BaseException:
        for target, content in backups.items():
            target.write_bytes(content)
        if (project / 'creative' / 'style.json') not in backups:
            (project / 'creative' / 'style.json').unlink(missing_ok=True)
        for target in created:
            target.unlink(missing_ok=True)
        raise
    pending = validation['status'] == 'pending'
    return {'status': 'applied', 'style': document['name'], 'template': template,
            'props': sorted(flatten(extra)) if extra else [], 'constraintsAdded': len(added),
            **({'music': props['music'].get('src')} if props.get('music') else {}),
            **({'arc': sorted(document['arc'])} if document.get('arc') else {}),
            **({'templateNotCovered': True} if template not in document.get('templates', {}) else {}),
            'next': ({'action': 'run', 'command': ['npm', 'run', 'music'], 'cwd': str(project)} if pending else
                     {'action': 'fix', 'hint': 'Follow the approved constraints in vvv.json; tag the photos and run arrange.'})}

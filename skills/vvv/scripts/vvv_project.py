"""Portable VVV project preparation, integrity checks and handoff inventory."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile

from PIL import Image

from vvv_assets import inventory_images, copy_normalized, contact_sheet, diagnostic

VERSION = '0.1'
FORMAT = '1.0'  # vvv.json written by this helper; 0.1 projects ("version": "0.1") stay readable
TEMPLATE_ID = re.compile(r'[a-z0-9][a-z0-9-]*')
FORMAT_ID = re.compile(r'[1-9][0-9]*:[1-9][0-9]*')
KIT_FILES = ['src', 'catalog', 'public', 'scripts', 'package.json', 'package-lock.json',
             'tsconfig.json', 'remotion.config.ts', 'ASSETS.md', 'font-sources.json',
             'LICENSE', 'MEDIA_LICENSE.md', 'THIRD_PARTY_NOTICES.md', 'package-licenses.json']
# What a render depends on. vvv.json is metadata (workflow notes, package fields) and is not fingerprinted.
FINGERPRINT_PATHS = ['inputs.json', 'assets.json', 'package.json', 'package-lock.json',
                     'tsconfig.json', 'remotion.config.ts', 'src', 'public', 'catalog', 'scripts']
PROPS_SCHEMA = 'schema/props.schema.json'
# The emotional vocabulary of a template's arc and of the photo tags an agent writes (vvv_arc).
MOODS = ('nostalgic', 'funny', 'sweet', 'romantic', 'moving', 'joyful')
SUBJECTS = ('groom', 'bride', 'couple', 'family', 'friends', 'other')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_text(path, text):
    """UTF-8 with LF line endings on every platform."""
    with open(path, 'w', encoding='utf-8', newline='\n') as output:
        output.write(text)


def write_json(path, value):
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def runtime_scripts(package):
    """package.json for a project or package: the kit's own tests stay in the kit."""
    if isinstance(package.get('scripts'), dict):
        package['scripts'] = {k: v for k, v in package['scripts'].items() if k != 'test'}
        package['scripts']['check'] = 'npm run typecheck && node scripts/prepare-fonts.mjs --verify'
    return package


def validate_catalog(catalog, template):
    """Check data consumed by initialization/validation before indexing its fields."""
    def fail(location, message):
        raise ValueError(f'CATALOG_INVALID: {location}: {message}')

    if not isinstance(catalog, dict):
        fail('catalog', 'Expected an object.')
    if catalog.get('id') != template:
        fail('id', 'Must match the selected template.')
    composition = catalog.get('compositionId')
    if not isinstance(composition, str) or not re.fullmatch(r'[A-Za-z0-9-]+', composition):
        fail('compositionId', 'Expected a nonempty composition ID containing letters, digits or hyphens.')
    if not isinstance(catalog.get('defaultProps'), dict):
        fail('defaultProps', 'Expected an object.')
    slots = catalog.get('slots')
    if not isinstance(slots, dict):
        fail('slots', 'Expected an object of named slot specifications.')
    for name, spec in slots.items():
        location = f'slots.{name}'
        if not isinstance(name, str) or not name:
            fail('slots', 'Slot names must be nonempty strings.')
        if not isinstance(spec, dict):
            fail(location, 'Expected a slot object.')
        groups = spec.get('groups')
        if groups is not None and (not isinstance(groups, list) or not groups or
                                   not all(isinstance(g, int) and g > 0 for g in groups) or sum(groups) != spec.get('count')):
            fail(f'{location}.groups', 'Expected positive group sizes that add up to count.')
        kind = spec.get('kind')
        if kind not in ('single', 'array', 'tokens'):
            fail(location + '.kind', 'Expected single, array or tokens.')
        for key in ['count', 'min', 'max']:
            if key != 'count' and key not in spec:
                continue
            value = spec.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                fail(location + '.' + key, 'Expected a nonnegative integer.')
        count = spec['count']
        minimum = spec.get('min', count)
        maximum = spec.get('max', count if kind == 'array' else None)
        if minimum > count or (maximum is not None and count > maximum):
            fail(location, 'Bounds must satisfy min <= count <= max when max is present.')
        if kind == 'single' and count != 1:
            fail(location + '.count', 'Single-photo slots require count 1.')
        if 'independent' in spec and not isinstance(spec['independent'], bool):
            fail(location + '.independent', 'Expected a boolean.')
    sample = catalog.get('sample')
    if not isinstance(sample, dict):
        fail('sample', 'Expected from/to times in seconds.')
    for key in ['from', 'to']:
        value = sample.get(key)
        try:
            finite = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        except OverflowError:
            finite = False
        if not finite:
            fail('sample.' + key, 'Expected a finite number of seconds.')
    if sample['from'] < 0 or sample['to'] <= sample['from']:
        fail('sample', 'Expected 0 <= from < to.')
    formats = catalog.get('formats')
    if not isinstance(formats, dict) or not formats:
        fail('formats', 'Expected an object of named frame sizes, for example {"16:9": {"width": 1920, "height": 1080}}.')
    for name, size in formats.items():
        location = f'formats.{name}'
        if not isinstance(name, str) or not FORMAT_ID.fullmatch(name):
            fail(location, 'Format names are aspect ratios such as 16:9 or 9:16.')
        if not isinstance(size, dict):
            fail(location, 'Expected width and height.')
        for key in ['width', 'height']:
            value = size.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0 or value % 2:
                fail(f'{location}.{key}', 'Expected a positive even number of pixels.')
        if 'sample' in size:
            # A format may have its own representative window, e.g. a shorter vertical cut.
            window = size['sample']
            if not isinstance(window, dict) or not all(
                    isinstance(window.get(k), (int, float)) and not isinstance(window.get(k), bool)
                    and math.isfinite(window.get(k)) for k in ('from', 'to')) or not 0 <= window['from'] < window['to']:
                fail(f'{location}.sample', 'Expected finite seconds with 0 <= from < to.')
        if 'slots' in size:
            # A format may use only some photo slots, e.g. a vertical short; the rest may stay empty.
            used = size['slots']
            if not isinstance(used, list) or not all(isinstance(n, str) and n in slots for n in used) or \
                    len(set(used)) != len(used):
                fail(f'{location}.slots', 'Expected a list of distinct slot names declared under slots.')
    if catalog.get('defaultFormat') not in formats:
        fail('defaultFormat', 'Must name one of the declared formats.')
    music = catalog.get('music', {})
    if not isinstance(music, dict) or not isinstance(music.get('required', False), bool):
        fail('music', 'Expected {"required": true|false}.')
    limits = catalog.get('check', {})
    if not isinstance(limits, dict):
        fail('check', 'Expected an object of check thresholds.')
    tracks = limits.get('tracks', [])
    if not isinstance(tracks, list) or not all(
            isinstance(x, dict) and isinstance(x.get('src'), str) and all(
                isinstance(x.get(k), (int, float)) and not isinstance(x.get(k), bool) for k in ('at', 'from')) for x in tracks):
        fail('check.tracks', 'Expected a list of {"src", "at", "from"} for later soundtrack tracks.')
    if catalog.get('kind', 'template') not in ('template', 'effect'):
        fail('kind', 'Expected template or effect.')
    if 'version' in catalog and (not isinstance(catalog['version'], str) or
                                 not re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-[0-9A-Za-z.-]+)?', catalog['version'])):
        fail('version', 'Expected a semantic version such as 1.0.0.')
    package = catalog.get('package')
    if package is not None and (not isinstance(package, dict) or
                                not re.fullmatch(r'@[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9-]*', str(package.get('name', '')))):
        fail('package', 'Expected {"name": "@scope/name", ...}.')
    if 'arc' in catalog:
        validate_arc(catalog['arc'], slots, fail)
    still = limits.get('maxStillSeconds', 3)
    if not isinstance(still, (int, float)) or isinstance(still, bool) or not math.isfinite(still) or still <= 0:
        fail('check.maxStillSeconds', 'Expected a positive number of seconds.')
    return catalog


def validate_arc(arc, slots, fail):
    """The arc lists the film's sections in playing order with the moods they want; every slot is in one section."""
    if not isinstance(arc, list) or not arc:
        fail('arc', 'Expected a nonempty list of sections.')
    seen, ids = set(), set()
    for index, section in enumerate(arc):
        location = f'arc[{index}]'
        if not isinstance(section, dict) or not isinstance(section.get('id'), str) or \
                not TEMPLATE_ID.fullmatch(section['id']) or section['id'] in ids:
            fail(location + '.id', 'Expected a unique lowercase section id.')
        ids.add(section['id'])
        if not isinstance(section.get('mood'), list) or not section['mood'] or \
                not all(m in MOODS for m in section['mood']):
            fail(location + '.mood', f'Expected a nonempty list of {", ".join(MOODS)}.')
        if section.get('order', 'input') not in ('input', 'chronological'):
            fail(location + '.order', 'Expected input or chronological.')
        if not isinstance(section.get('slots'), list) or not section['slots']:
            fail(location + '.slots', 'Expected a nonempty list of slot names.')
        for entry in section['slots']:
            spec = {'slot': entry} if isinstance(entry, str) else entry
            name = spec.get('slot') if isinstance(spec, dict) else None
            if name not in slots or name in seen:
                fail(location + '.slots', f'{name!r} is not a declared slot, or is in two sections.')
            seen.add(name)
            if not all(m in MOODS for m in spec.get('mood', [])) or not all(x in SUBJECTS for x in spec.get('subject', [])) \
                    or not isinstance(spec.get('pin', False), bool):
                fail(f'{location}.slots.{name}', 'Unknown mood or subject, or a non-boolean pin.')
    if seen != set(slots):
        fail('arc', 'Every slot must be in exactly one section; missing: ' + ', '.join(sorted(set(slots) - seen)))


def format_arc(catalog, frame_format):
    """The arc for one format: its sections with only the slots the format uses, empty sections dropped."""
    used = set(format_slots(catalog, frame_format))
    arc = []
    for section in catalog.get('arc') or []:
        entries = [{'slot': e} if isinstance(e, str) else dict(e) for e in section['slots']]
        entries = [e for e in entries if e['slot'] in used]
        if entries:
            arc.append({**section, 'slots': entries})
    return arc


def kit_root(kit):
    kit = Path(kit).expanduser().resolve()
    if not (kit / 'catalog').is_dir():
        raise ValueError(f'KIT_NOT_FOUND: {kit} has no catalog/ directory; pass the kit directory (for example kits/remotion).')
    return kit


def photo_needs(catalog, frame_format):
    """Distinct photos a format needs at least, and its target: shared slots add up, independent slots reuse."""
    slots = catalog['slots']
    used = format_slots(catalog, frame_format)
    shared = [slot_bounds(slots[n]) for n in used if not slots[n].get('independent')]
    independent = [slot_bounds(slots[n]) for n in used if slots[n].get('independent')]
    return (max(sum(b[1] for b in shared), max((b[1] for b in independent), default=0)),
            max(sum(b[0] for b in shared), max((b[0] for b in independent), default=0)))


def format_entries(catalog):
    entries = []
    for name, size in catalog['formats'].items():
        minimum, target = photo_needs(catalog, name)
        entries.append({'name': name, 'width': size['width'], 'height': size['height'],
                        'minPhotos': minimum, 'targetPhotos': target})
    return entries


def list_templates(kit, kind='template'):
    """Templates (or effects) are the kit's catalog files; each file name is the ID."""
    kit = kit_root(kit)
    found = []
    for path in sorted((kit / 'catalog').glob('*.json')):
        if not TEMPLATE_ID.fullmatch(path.stem):
            continue
        catalog = validate_catalog(read_json(path), path.stem)
        if catalog.get('kind', 'template') != kind:
            continue
        found.append({'id': path.stem, 'title': catalog.get('title', path.stem),
                      'description': catalog.get('description', ''), 'formats': format_entries(catalog),
                      'defaultFormat': catalog['defaultFormat'],
                      'musicRequired': catalog.get('music', {}).get('required', False)})
    return found


def schema_type(node):
    if not isinstance(node, dict):
        return None
    if 'type' in node:
        return node['type']
    types = [schema_type(n) for n in node.get('anyOf', [])]
    return ' | '.join(sorted({t for t in types if isinstance(t, str)})) or None


def describe_template(kit, template, frame_format=None, script='scripts/vvv.py'):
    """One compact record with what an agent needs to fill a template's inputs, without reading its source.
    `next` commands use `script` and the kit path as given, so they run from the caller's directory."""
    if str(template).endswith('.vvv'):
        import zipfile
        from vvv_package import verify_package
        report = verify_package(Path(template).expanduser())
        if report['status'] == 'failed':
            raise ValueError('PACKAGE_INVALID: ' + '; '.join(c['code'] + ': ' + c['message'] for c in report['checks']
                                                              if c['status'] == 'failed'))
        with zipfile.ZipFile(Path(template).expanduser()) as archive:
            manifest = json.loads(archive.read('vvv.json'))
            if manifest.get('kind') not in ('template', 'effect'):
                raise ValueError(f"PACKAGE_KIND: describe needs a template package; this is a {manifest.get('kind')} package.")
            catalog = validate_catalog(json.loads(archive.read(manifest['template']['catalog'])), manifest['template']['id'])
            schema = json.loads(archive.read(manifest['schema'])) if manifest.get('schema') in archive.namelist() else {}
        fixture, root = manifest.get('inputs', 'inputs.json'), None
        source = ['--template', str(template)]
    else:
        root = kit_root(kit)
        catalog = load_catalog(root, template)
        path = root / 'schema' / f'{template}.json'
        schema = read_json(path) if path.is_file() else {}
        fixture = (catalog.get('package') or {}).get('fixture')
        source = ['--kit', str(kit), '--template', template]
    frame_format = frame_format or catalog['defaultFormat']
    if frame_format not in catalog['formats']:
        raise ValueError(f'UNSUPPORTED_FORMAT: {catalog["id"]} supports {", ".join(catalog["formats"])}; got {frame_format}.')
    used = format_slots(catalog, frame_format)
    # Compact: a single slot takes exactly one photo; min and max appear only when they differ from count;
    # independent only when true; unused slots are listed by name.
    slots = []
    for name in used:
        spec = catalog['slots'][name]
        count, minimum, maximum = slot_bounds(spec)
        bounds = {} if spec['kind'] == 'single' else {
            **({'min': minimum} if minimum != count else {}), 'count': count,
            **({'max': maximum} if maximum is not None and maximum != count else {})}
        slots.append({'name': name, 'kind': spec['kind'], **bounds,
                      **({'independent': True} if spec.get('independent') else {}),
                      **({'hint': spec['hint']} if isinstance(spec.get('hint'), str) else {})})
    properties = schema.get('properties') if isinstance(schema.get('properties'), dict) else {}

    def labels(name):
        node = properties.get(name)
        fields = node.get('properties') if isinstance(node, dict) else None
        if isinstance(fields, dict):
            return {k: (v.get('description') or '') if isinstance(v, dict) else '' for k, v in fields.items()}
        default = catalog['defaultProps'].get(name)
        return {k: '' for k in default} if isinstance(default, dict) else None

    music = catalog['defaultProps'].get('music') if isinstance(catalog['defaultProps'].get('music'), dict) else {}
    music_download = download_track(root, music['src']) if root and music.get('src') else None
    formats = format_entries(catalog)
    for entry in formats:
        entry['sample'] = catalog['formats'][entry['name']].get('sample') or catalog['sample']
    arc = [{'id': x['id'], 'mood': x['mood'], **({'order': x['order']} if x.get('order') == 'chronological' else {}),
            'slots': [e['slot'] if len(e) == 1 else e for e in x['slots']]} for x in format_arc(catalog, frame_format)]
    chosen = [] if frame_format == catalog['defaultFormat'] else ['--format', frame_format]
    command = f'python3 {script} init ' + ' '.join(source + chosen)
    # Pages in beats become seconds only with a song: report them at the default track, so a rushed
    # template shows before rendering. `music fit` recomputes them for the project's own track.
    extra = {}
    if isinstance(catalog.get('shows'), dict):
        extra['shows'] = catalog['shows']
    if isinstance(catalog.get('timeline'), dict):
        timeline = catalog['timeline']
        extra['timeline'] = {'climax': timeline.get('climax'), 'pace': timeline.get('pace'),
                             'pages': [f"{p['id']}:{p['beats']}" for p in timeline.get('pages', [])]}
        beats_file = root / 'public' / Path(music['src']).with_suffix('.beats.json') if root and music.get('src') else None
        if beats_file and beats_file.is_file():
            from vvv_music import timing
            extra['timing'] = {'track': music['src'], **timing(catalog, read_json(beats_file))}
    return {'status': 'passed', 'id': catalog['id'], 'kind': catalog.get('kind', 'template'),
            'title': catalog.get('title', catalog['id']), 'description': catalog.get('description', ''),
            'defaultFormat': catalog['defaultFormat'], 'format': frame_format, 'formats': formats, 'slots': slots,
            'unusedSlots': [n for n in catalog['slots'] if n not in used],
            'copy': labels('copy') or {}, 'couple': labels('couple'),
            'props': {k: {'type': schema_type(v), **({'description': v['description']} if v.get('description') else {}),
                          **({'enum': v['enum']} if 'enum' in v else {})}
                      for k, v in properties.items() if isinstance(v, dict) and
                      k not in ('photos', 'copy', 'couple', 'fps', 'format', 'music')},
            'music': {'required': bool(catalog.get('music', {}).get('required')), 'src': music.get('src', ''),
                      **({'downloadOnly': music_download} if music_download is not None else {})},
            'fixture': fixture, **({'arc': arc} if arc else {}), **extra,
            'next': [command + ' --photos PHOTOS_DIR --output PROJECT', command + ' --example --output PROJECT']}


def load_catalog(root, template):
    if not isinstance(template, str) or not TEMPLATE_ID.fullmatch(template):
        raise ValueError(f'UNKNOWN_TEMPLATE: {template}')
    path = Path(root) / 'catalog' / f'{template}.json'
    if not path.is_file():
        raise ValueError(f'UNKNOWN_TEMPLATE: {template}')
    return validate_catalog(read_json(path), template)


def safe_public_path(project, relative):
    if not isinstance(relative, str) or not relative or '\\' in relative:
        raise ValueError('Expected a nonempty public-relative path.')
    posix = PurePosixPath(relative)
    if posix.is_absolute() or '..' in posix.parts or re.match(r'^[A-Za-z]:', relative):
        raise ValueError('Path escapes the project public directory.')
    public = Path(project).resolve() / 'public'
    if public.is_symlink():
        raise ValueError('The project public directory must not be a symbolic link.')
    target = public / relative
    current = public
    for part in posix.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('Asset paths must not contain symbolic links.')
    if public not in target.resolve().parents:
        raise ValueError('Asset path or symbolic link escapes the public directory.')
    return target


def format_slots(catalog, frame_format):
    """Slot names a format uses: its formats[f].slots when declared, otherwise every slot."""
    used = (catalog['formats'].get(frame_format) or {}).get('slots')
    return [name for name in catalog['slots'] if used is None or name in used]


def slot_bounds(spec):
    count = int(spec['count'])
    return count, int(spec.get('min', count)), spec.get('max', count if spec['kind'] == 'array' else None)


def slot_takes(catalog, available, allow_repeat, frame_format):
    """How many photos each shared (non-independent) slot of a format takes from `available` distinct photos:
    every slot its minimum first, then spare photos toward each slot's count, in slot order."""
    slots = catalog['slots']
    used = set(format_slots(catalog, frame_format))
    shared = [name for name in slots if name in used and not slots[name].get('independent')]
    take = {name: slot_bounds(slots[name])[1] for name in shared}
    needed = sum(take.values())
    if needed > available and not allow_repeat:
        detail = ', '.join(f'{name} {take[name]}' for name in shared if take[name])
        raise ValueError(f'INSUFFICIENT_PHOTOS: {catalog["id"]} ({frame_format}) needs at least {needed} distinct photos '
                         f'({detail}); got {available}. Provide more photos, adapt the scene, or explicitly use --allow-repeat.')
    spare = max(0, available - needed)
    for name in shared:
        extra = min(spare, slot_bounds(slots[name])[0] - take[name])
        take[name] += extra
        spare -= extra
    return shared, take


def bind_photos(catalog, assets, allow_repeat=False, frame_format=None):
    """Assign photos in input order. Every slot the format uses gets its minimum first; spare photos
    then fill slots toward their target count, in slot order. Independent slots (galleries) prefer photos
    no other slot uses, then reuse others; they keep input order."""
    ids = [a['id'] for a in assets]
    slots = catalog['slots']
    result, diagnostics = {}, []
    if not slots:
        return result, diagnostics
    if not ids:
        raise ValueError('NO_USABLE_PHOTOS: No supported, decodable photos were found.')
    frame_format = frame_format or catalog['defaultFormat']
    used = set(format_slots(catalog, frame_format))
    shared, take = slot_takes(catalog, len(ids), allow_repeat, frame_format)
    picks, wrapped, cursor = {}, set(), 0
    for name in shared:
        picks[name] = [ids[(cursor + i) % len(ids)] for i in range(take[name])]
        cursor += take[name]
        if cursor > len(ids) and picks[name]:
            wrapped.add(name)
    taken = {i for picked in picks.values() for i in picked}
    order = {photo: index for index, photo in enumerate(ids)}
    for name, slot in slots.items():
        if name in picks or name not in used:
            continue
        count, minimum, _ = slot_bounds(slot)
        chosen = ([i for i in ids if i not in taken] + [i for i in ids if i in taken])[:count]
        picked = sorted(chosen, key=order.get)
        while len(picked) < minimum:
            picked.append(ids[len(picked) % len(ids)])
        picks[name] = picked
        taken.update(picked)
    for name, slot in slots.items():
        picked = picks.get(name, [])
        if len(set(picked)) < len(picked) or name in wrapped:
            diagnostics.append(diagnostic('PHOTO_REUSED', 'Photo reuse was explicitly enabled.', f'props.photos.{name}'))
        kind = slot['kind']
        result[name] = (picked[0] if picked else '') if kind == 'single' else (
            ' '.join('@' + item for item in picked) if kind == 'tokens' else picked)
    unused = len(set(ids) - taken)
    if unused:
        diagnostics.append(diagnostic('PHOTOS_UNUSED', f'{unused} photos fill no slot; slots stop at their target count. '
                                      'Raise a slot toward its max in inputs.json to use more.', 'props.photos', 'info'))
    return result, diagnostics


def copy_kit(kit, destination):
    """The kit's runtime files; its own tests stay behind so npm run check works in the project."""
    for name in KIT_FILES:
        source = kit / name
        if not source.exists():
            continue
        paths = [source] + (list(source.rglob('*')) if source.is_dir() else [])
        for path in paths:
            if path.is_symlink():
                raise ValueError(f'KIT_SYMLINK: Kit distribution contains a symbolic link: {path.relative_to(kit)}')
        if source.is_dir():
            def ignore(directory, names):
                return [n for n in names if n in {'.DS_Store', '__pycache__', 'node_modules'} or
                        n.endswith(('.test.cjs', '.test.mjs')) or (Path(directory) == kit / 'public' and n == 'photos')]
            shutil.copytree(source, destination / name, ignore=ignore)
        elif name == 'package.json':
            write_json(destination / name, runtime_scripts(read_json(source)))
        else:
            shutil.copy2(source, destination / name)


KIT_BASELINE = 'kit-files.json'
KIT_SKIP = {'.DS_Store', '__pycache__', 'node_modules'}


def kit_snapshot(kit, template):
    """What init copies from the kit, as {project path: bytes reader}: the runtime files, the template's
    props schema, and package.json with the project's own scripts."""
    files = {}
    for name in KIT_FILES:
        source = kit / name
        if not source.exists():
            continue
        if source.is_dir():
            for path in sorted(source.rglob('*')):
                parts = path.relative_to(kit).parts
                if (path.is_file() and not any(p in KIT_SKIP for p in parts) and not path.name.endswith(('.test.cjs', '.test.mjs'))
                        and parts[:2] != ('public', 'photos')):
                    files[path.relative_to(kit).as_posix()] = path.read_bytes
        elif name == 'package.json':
            files[name] = lambda source=source: (json.dumps(runtime_scripts(read_json(source)), ensure_ascii=False, indent=2) + '\n').encode()
        else:
            files[name] = source.read_bytes
    schema = kit / 'schema' / f'{template}.json'
    if schema.is_file():
        files[PROPS_SCHEMA] = schema.read_bytes
    return files


def write_kit_baseline(project, kit, template):
    """Record the hash of every kit file as copied, so update can tell kit changes from local edits."""
    hashes = {}
    for rel in kit_snapshot(kit, template):
        target = project / rel
        if target.is_file():
            hashes[rel] = hashlib.sha256(target.read_bytes()).hexdigest()
    write_json(project / KIT_BASELINE, {'version': '0.1', 'template': template, 'files': hashes})


def update_project(project, kit, apply=False, take_kit=False):
    """Bring a project's template code and kit files up to date: three-way by file (kit now, project now,
    kit as copied). Unchanged files take the kit's version; files edited in the project are conflicts and
    stay, unless take_kit. Without apply it only reports."""
    project = Path(project).expanduser().resolve()
    root = kit_root(kit)
    template = read_json(project / 'inputs.json')['template']
    load_catalog(root, template)
    baseline_path = project / KIT_BASELINE
    baseline = read_json(baseline_path).get('files', {}) if baseline_path.is_file() else {}
    report = {'updated': [], 'added': [], 'conflicts': [], 'unchanged': 0}
    snapshot = kit_snapshot(root, template)
    pending = []
    for rel, read in snapshot.items():
        data = read()
        new = hashlib.sha256(data).hexdigest()
        target = safe_output_path(project, rel) if rel != PROPS_SCHEMA else project / PROPS_SCHEMA
        if not target.exists():
            report['added'].append(rel)
            pending.append((target, data, rel, new))
            continue
        if target.is_symlink() or not target.is_file():
            raise ValueError(f'PROJECT_SYMLINK: {rel} must be a regular file.')
        current = hashlib.sha256(target.read_bytes()).hexdigest()
        if current == new:
            report['unchanged'] += 1
            baseline[rel] = new
        elif baseline.get(rel) == current:
            report['updated'].append(rel)
            pending.append((target, data, rel, new))
        else:
            report['conflicts'].append(rel)
            if take_kit:
                pending.append((target, data, rel, new))
    if apply:
        for target, data, rel, digest in pending:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            baseline[rel] = digest
        write_json(baseline_path, {'version': '0.1', 'template': template, 'files': baseline})
    result = {'status': 'passed', 'applied': apply, **{k: (v if isinstance(v, int) else v[:40]) for k, v in report.items()},
              'counts': {k: len(v) for k, v in report.items() if isinstance(v, list)}}
    if not baseline_path.is_file() and not apply:
        result['note'] = 'No kit-files.json (a project from before update existed): every difference is a conflict.'
    if report['conflicts'] and not take_kit:
        result['next'] = {'action': 'fix', 'hint': 'Conflicts are files edited in the project and changed in the kit. Diff each, '
                          'carry the kit change into the local edit by hand, or rerun with --take-kit to discard the local edits.'}
    if apply:
        result['validation'] = validate_project(project)['status']
    return result


def example_inputs(root, catalog, template):
    """The template's shipped demo inputs (catalog package.fixture) and the kit photo records they name."""
    relative = (catalog.get('package') or {}).get('fixture')
    if not isinstance(relative, str) or not relative:
        raise ValueError(f'EXAMPLE_MISSING: {template} ships no example inputs (catalog package.fixture).')
    posix = PurePosixPath(relative)
    if posix.is_absolute() or '..' in posix.parts or '\\' in relative or not (root / relative).is_file():
        raise ValueError(f'EXAMPLE_MISSING: {relative} is not a file inside the kit.')
    fixture = read_json(root / relative)
    if not isinstance(fixture, dict) or not isinstance(fixture.get('props'), dict) or \
            fixture.get('template', template) != template:
        raise ValueError(f'EXAMPLE_INVALID: {relative} must be {{"template": "{template}", "props": {{...}}}}.')
    document = read_json(root / 'assets.json') if (root / 'assets.json').is_file() else {}
    items = [i for i in (document.get('items') or []) if isinstance(i, dict) and isinstance(i.get('id'), str)]
    from vvv_package import referenced_ids
    used = referenced_ids(fixture['props'], {i['id'] for i in items})
    return relative, deepcopy(fixture['props']), [deepcopy(i) for i in items if i['id'] in used]


def heic_note(error, diagnostics):
    skipped = sum(d['code'] == 'HEIC_UNSUPPORTED' for d in diagnostics)
    text = str(error)
    if skipped and text.startswith(('INSUFFICIENT_PHOTOS', 'NO_USABLE_PHOTOS')):
        return ValueError(f'{text} {skipped} HEIC/HEIF photos could not be read: convert them to JPEG or install pillow-heif.')
    return error


def create_project(kit, template, sources, output, allow_repeat=False, frame_format=None, example=False,
                   max_size=None, faces=False):
    """Create a project from a kit template ID, or from a template package when `template` is a .vvv file.
    With `example`, the project uses the template's shipped demo inputs and photos instead of `sources`."""
    package = Path(template).expanduser() if str(template).endswith('.vvv') else None
    output = Path(output).expanduser().absolute()
    if output.exists() or output.is_symlink():
        raise ValueError(f'DESTINATION_EXISTS: {output.name}')
    if example and sources:
        raise ValueError('EXAMPLE_WITH_PHOTOS: Pass either --example or --photos.')
    fixture_rel, props, items = None, None, []
    if package:
        from vvv_package import verify_package
        report = verify_package(package)
        if report['status'] == 'failed':
            raise ValueError('PACKAGE_INVALID: ' + '; '.join(c['code'] + ': ' + c['message'] for c in report['checks']
                                                              if c['status'] == 'failed'))
        if report['package']['kind'] != 'template':
            raise ValueError(f"PACKAGE_KIND: init needs a template package; this is a {report['package']['kind']} package. "
                             'Use unpack for projects and add for effects.')
        template = report['package']['template']['id']
        origin = f"{report['package']['name']}@{report['package']['version']}"
    else:
        kit = kit_root(kit)
        catalog = load_catalog(kit, template)
        if catalog.get('kind', 'template') != 'template':
            raise ValueError(f'NOT_A_TEMPLATE: {template} is an effect; add it to a project with the add command.')
        if example:
            fixture_rel, props, items = example_inputs(kit, catalog, template)
        frame_format = frame_format or (props or {}).get('format') or catalog['defaultFormat']
        if frame_format not in catalog['formats']:
            raise ValueError(f'UNSUPPORTED_FORMAT: {template} supports {", ".join(catalog["formats"])}; got {frame_format}.')
        if not sources and not example and catalog['slots']:
            raise ValueError(f'PHOTOS_REQUIRED: {template} has photo slots; pass --photos, or --example for the demo.')
    found, diagnostics = inventory_images(sources) if sources else ([], [])
    if any(d['severity'] == 'error' for d in diagnostics):
        raise ValueError('SOURCE_MISSING: One or more explicitly supplied sources do not exist.')
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f'.{output.name}-', dir=output.parent))
    try:
        if package:
            from vvv_package import extract_into
            extract_into(package, temporary)
            # The package's publication records describe the template, not this project; so do its demo inputs
            # and photos unless the project is the example.
            removed = ('integrity.json', 'licenses.json', 'check', 'preview') + (() if example else ('inputs.json', 'assets.json'))
            for name in removed:
                target = temporary / name
                shutil.rmtree(target) if target.is_dir() else target.unlink(missing_ok=True)
            if not example:
                shutil.rmtree(temporary / 'public' / 'photos', ignore_errors=True)
            catalog = load_catalog(temporary, template)
            if example:
                fixture_rel = 'inputs.json'
                demo = read_json(temporary / 'inputs.json')
                props = demo.get('props') if isinstance(demo, dict) and isinstance(demo.get('props'), dict) else {}
                items = (read_json(temporary / 'assets.json').get('items') or []) if (temporary / 'assets.json').is_file() else []
            frame_format = frame_format or (props or {}).get('format') or catalog['defaultFormat']
            if frame_format not in catalog['formats']:
                raise ValueError(f'UNSUPPORTED_FORMAT: {template} supports {", ".join(catalog["formats"])}; got {frame_format}.')
            if not sources and not example and catalog['slots']:
                raise ValueError(f'PHOTOS_REQUIRED: {template} has photo slots; pass --photos, or --example for the demo.')
        if not example:
            try:
                mapping, reused = bind_photos(catalog, found, allow_repeat, frame_format)
            except ValueError as error:
                raise heic_note(error, diagnostics) from None
            diagnostics.extend(reused)
        if not package:
            copy_kit(kit, temporary)
            # The same props schema a .vvv template package carries, generated from the template's zod schema.
            schema = kit / 'schema' / f'{template}.json'
            if schema.is_file():
                (temporary / 'schema').mkdir()
                shutil.copy2(schema, temporary / PROPS_SCHEMA)
            for item in items:
                target = safe_public_path(temporary, item.get('file'))
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(safe_public_path(kit, item['file']), target)
        public = temporary / 'public'
        public.mkdir(exist_ok=True)
        if example:
            assets = items
            props.setdefault('fps', 30)
        else:
            from vvv_assets import MAX_SIZE, detect_faces
            if faces and detect_faces(Image.new('RGB', (8, 8))) is None:
                diagnostics.append(diagnostic('FACES_UNAVAILABLE', 'Face detection needs OpenCV (opencv-python-headless), '
                                              'which is not installed; photos are cropped around their upper middle. '
                                              'Ask the user before installing it.'))
            assets = copy_normalized(found, public, MAX_SIZE if max_size is None else max_size, faces)
            props = deepcopy(catalog['defaultProps'])
            props['photos'] = mapping
            props['fps'] = int(props.get('fps', 30))
        props['format'] = frame_format
        write_json(temporary / 'assets.json', {'version': VERSION, 'items': assets})
        write_json(temporary / 'inputs.json', {'template': template, 'props': props})
        remotion = read_json(temporary / 'package.json').get('dependencies', {}).get('remotion')
        manifest = {'vvvFormat': FORMAT, 'kind': 'project', 'id': output.name, 'version': '0.1.0',
                    'template': {'id': template, 'version': catalog.get('version', '0.1.0'),
                                 **({'from': origin} if package else {})},
                    'entry': 'src/index.tsx', 'inputs': 'inputs.json', 'assets': 'assets.json',
                    'runtime': {'engine': 'remotion', 'version': remotion},
                    'workflow': {'mode': 'sample-first', 'stage': 'draft', 'approvedConstraints': []}}
        write_json(temporary / 'vvv.json', manifest)
        if not package:
            write_kit_baseline(temporary, kit, template)
        # Kit and package projects get the same agent notes; project instructions go outside the generated block.
        from vvv_package import agents_text, project_agents
        (temporary / 'AGENTS.md').write_bytes(project_agents(None, agents_text(manifest, 'PROJECT.md')))
        (temporary / 'CLAUDE.md').write_bytes(b'@AGENTS.md\n')
        creative = temporary / 'creative'
        creative.mkdir(exist_ok=True)
        if example:
            write_json(creative / 'intake.json', {'selection': 'example', 'example': fixture_rel,
                                                 'note': 'Fictional demo photos and copy; replace them before personal delivery.',
                                                 'photos': [a['id'] for a in assets]})
        else:
            write_json(creative / 'intake.json', {'selection': 'input order; review semantic slot assignment',
                                                 'allowRepeat': allow_repeat, 'diagnostics': diagnostics,
                                                 'sources': [a['source'] for a in assets]})
        if assets:
            contact_sheet(assets, public, creative / 'contact-sheet.jpg')
        write_text(temporary / '.gitignore', 'node_modules/\nout/\nbuild/\n.DS_Store\n'
                   '# Download-only music and effects; fetched by npm run music\npublic/music/mixkit-*.mp3\npublic/sfx/mixkit-*.wav\n')
        state = (f'It uses the template\'s fictional example inputs (`{fixture_rel}`): demo photos and copy, correctly mapped.'
                 if example else 'This is a draft with provisional photo-slot assignments.')
        write_text(temporary / 'PROJECT.md',
            '# VVV editable project\n\n'
            f'Template: `{template}`, format `{frame_format}`. {state}\n\n'
            '- Review `creative/contact-sheet.jpg` and `inputs.json`; do not infer people or events from slot names.\n'
            '- Replace any demonstration names, dates and copy before personal delivery.\n'
            '- Edit the actual template under `src/templates/`; the original installed kit is unchanged.\n'
            '- `npm ci`, then `npm run music` fetches any download-only track the inputs reference.\n'
            '- `npm run studio` opens the interactive project.\n'
            '- `npm run sample` renders the catalog time range of this main composition.\n'
            '- After sample feedback, use `npm run render` for the full composition.\n'
            '- `vvv.py validate --project .` checks `inputs.json` against `schema/props.schema.json` and the photo slots. '
            'If you change a template\'s props in `src/`, regenerate the schema: '
            f'`node scripts/export-schemas.cjs {template} schema/props.schema.json`.\n'
            '- Keep approved creative choices in `vvv.json` under `workflow.approvedConstraints`, and project-specific agent '
            'instructions in `AGENTS.md` outside its generated block; packing keeps them.\n'
            '- Keep actual generated files in `public/` and record their provenance.\n'
            '- Output reports identify the source revision and sampled frame range.\n')
        checks = validate_project(temporary, verbose=True)
        if checks['status'] == 'failed':
            errors = [c['code'] + ': ' + c['message'] for c in checks['checks'] if c['status'] == 'failed']
            raise ValueError('PROJECT_INVALID: ' + '; '.join(errors))
        if output.exists():
            raise ValueError(f'DESTINATION_EXISTS: {output.name}')
        temporary.rename(output)
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return {'status': 'created', 'project': str(output), 'template': template, 'format': frame_format,
            'assetCount': len(assets), **({'example': fixture_rel} if example else {}), 'diagnostics': diagnostics,
            'pending': [c['message'] for c in checks['checks'] if c['status'] == 'pending'],
            'next': ('Run npm ci inside the project' + (', then npm run music' if checks['status'] == 'pending' else '') +
                     ', then npm run sample.') if example else
                    'Review the contact sheet and inputs, then npm ci inside the project.' +
                    (' Then run npm run music.' if checks['status'] == 'pending' else '')}


def concise(report, verbose=False):
    """By default list only checks that did not pass (failed, pending, warning) and count the rest."""
    checks = report.get('checks', [])
    if verbose:
        return dict(report, passed=sum(c['status'] == 'passed' for c in checks))
    return dict(report, passed=sum(c['status'] == 'passed' for c in checks),
                checks=[c for c in checks if c['status'] != 'passed'])


def validate_project(project, verbose=False):
    """Status is failed, pending (download-only files missing) or passed; warnings do not change it."""
    project = Path(project).expanduser().resolve()
    checks = []
    def check(code, message, location='', ok=False, success=None):
        checks.append({'code': code, 'message': (success or message) if ok else message, 'location': location,
                       'status': 'passed' if ok else 'failed'})
    def failed():
        return concise({'status': 'failed', 'checks': checks}, verbose)
    try:
        project_source_files(project)
    except ValueError as error:
        check('PROJECT_SYMLINK', str(error))
        return failed()
    except OSError as error:
        check('PROJECT_PATH_UNREADABLE', str(error))
        return failed()
    try:
        manifest = read_json(project / 'vvv.json')
        assets_document = read_json(project / 'assets.json')
        inputs = read_json(project / 'inputs.json')
        if not isinstance(manifest, dict) or not isinstance(inputs, dict) or not isinstance(assets_document, dict):
            raise ValueError('Project documents must be JSON objects.')
    except (OSError, ValueError) as error:
        check('PROJECT_JSON', str(error))
        return failed()
    known = manifest.get('vvvFormat') == FORMAT or (manifest.get('vvvFormat') is None and manifest.get('version') == VERSION)
    check('UNSUPPORTED_VERSION' if not known else 'VERSION',
          f'Expected vvvFormat {FORMAT} (or a 0.1 project).', 'vvv.json.vvvFormat', known,
          f'vvv.json is a supported project format ({manifest.get("vvvFormat") or manifest.get("version")}).')
    check('ASSET_VERSION', 'Expected asset format 0.1.', 'assets.json.version',
          assets_document.get('version') == VERSION, 'assets.json is asset format 0.1.')
    template = inputs.get('template')
    if not isinstance(template, str) or not TEMPLATE_ID.fullmatch(template) or \
            not (project / 'catalog' / f'{template}.json').is_file():
        check('UNKNOWN_TEMPLATE', 'Unknown template.', 'inputs.json.template')
        return failed()
    check('TEMPLATE_MATCH', 'vvv.json and inputs.json name different templates.', 'vvv.json.template',
          isinstance(manifest.get('template'), dict) and manifest['template'].get('id') == template,
          'Project and input template agree.')
    try:
        catalog = validate_catalog(read_json(project / 'catalog' / f'{template}.json'), template)
    except OSError as error:
        check('CATALOG_MISSING', str(error))
        return failed()
    except ValueError as error:
        check('CATALOG_INVALID', str(error), f'catalog/{template}.json')
        return failed()
    items = assets_document.get('items')
    if not isinstance(items, list):
        check('ASSET_LIST', 'Asset items must be an array.', 'assets.json.items')
        items = []
    ids = set()
    for index, asset in enumerate(items):
        loc = f'assets.json.items[{index}]'
        if not isinstance(asset, dict) or not isinstance(asset.get('id'), str) or not asset['id']:
            check('ASSET_ID', 'Asset requires a nonempty string ID.', loc)
            continue
        if asset['id'] in ids:
            check('DUPLICATE_ASSET_ID', 'Each asset ID must be unique.', loc)
        ids.add(asset['id'])
        try:
            path = safe_public_path(project, asset.get('file'))
        except ValueError as error:
            check('ASSET_PATH_UNSAFE', str(error), loc)
            continue
        if not path.is_file():
            check('ASSET_MISSING', f"Missing asset {asset.get('file')}", loc)
            continue
        try:
            with Image.open(path) as image:
                image.load()
                if image.size != (asset.get('width'), asset.get('height')):
                    check('ASSET_DIMENSIONS', 'Declared image size differs from decoded image.', loc)
                else:
                    check('ASSET_DECODED', 'Image decoded with matching dimensions.', loc, True)
        except (OSError, ValueError, Image.DecompressionBombError) as error:
            check('ASSET_UNREADABLE', str(error), loc)
    props = inputs.get('props')
    if not isinstance(props, dict):
        check('INPUT_PROPS', 'props must be an object.', 'inputs.json.props')
        props = {}
    fps = props.get('fps')
    check('FPS', 'fps must be an integer from 24 to 60.', 'inputs.json.props.fps',
          isinstance(fps, int) and not isinstance(fps, bool) and 24 <= fps <= 60, f'fps {fps} is supported.')
    frame_format = props.get('format', catalog['defaultFormat'])
    check('FORMAT', f'format must be one of {", ".join(catalog["formats"])}.', 'inputs.json.props.format',
          isinstance(frame_format, str) and frame_format in catalog['formats'], f'Format {frame_format} is supported.')
    photos = props.get('photos', {})
    if not isinstance(photos, dict):
        check('PHOTO_SLOTS', 'photos must be an object.', 'inputs.json.props.photos')
        photos = {}
    used = set(format_slots(catalog, frame_format) if isinstance(frame_format, str) and frame_format in catalog['formats']
               else catalog['slots'])
    for name, spec in catalog.get('slots', {}).items():
        loc = f'inputs.json.props.photos.{name}'
        value = photos.get(name)
        kind = spec['kind']
        if kind == 'single':
            if not isinstance(value, str):
                check('SLOT_TYPE', 'Expected a photo ID string; use "" for a slot this format leaves out.', loc)
                continue
            selected = [value] if value else []
        elif kind == 'array':
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                check('SLOT_TYPE', 'Expected an array of photo IDs.', loc)
                continue
            selected = value
        elif kind == 'tokens':
            if not isinstance(value, str):
                check('SLOT_TYPE', 'Expected photo tokens, optionally prefixed with @.', loc)
                continue
            # Match DV Story's parsePages/photoIdFromToken grammar. Page boundaries
            # affect the runtime timeline; validation only flattens them to resolve IDs.
            tokens = [token for token in re.split(r'[|,，\s]+', value) if token]
            if any(not re.fullmatch(r'@?[A-Za-z0-9][A-Za-z0-9_-]*', token) for token in tokens):
                check('PHOTO_TOKEN', 'Use asset IDs with an optional @; separate photos with '
                      'whitespace or commas and pages with |.', loc)
                continue
            selected = [t[1:] if t.startswith('@') else t for t in tokens]
        else:
            check('SLOT_KIND', f'Unknown slot kind {kind}', loc)
            continue
        _, minimum, maximum = slot_bounds(spec)
        if name not in used:
            minimum = 0  # this format does not show the slot
        if len(selected) < minimum or (maximum is not None and len(selected) > maximum):
            check('SLOT_COUNT', f'Expected {minimum}..{maximum if maximum is not None else "unbounded"} photo IDs'
                  f'{"" if name in used else f" ({frame_format} does not use this slot)"}.', loc)
        for photo in selected:
            if not isinstance(photo, str) or photo not in ids:
                check('UNKNOWN_PHOTO_ID', f'Unknown photo ID: {photo}', loc)
    music = props.get('music', {})
    if not isinstance(music, dict):
        check('MUSIC_TYPE', 'music must be an object.', 'inputs.json.props.music')
    elif not isinstance(music.get('src'), str):
        check('MUSIC_TYPE', 'music.src must be a string; use an empty string for silence.',
              'inputs.json.props.music.src')
    elif music.get('src'):
        try:
            path = safe_public_path(project, music['src'])
            if not path.is_file() and download_track(project, music['src']):
                checks.append({'code': 'MUSIC_DOWNLOAD_PENDING', 'status': 'pending',
                               'location': 'inputs.json.props.music.src',
                               'message': f"{music['src']} is download-only; run npm run music in the project."})
            else:
                check('MUSIC_FILE', f"Music file public/{music['src']} is missing.", 'inputs.json.props.music.src',
                      path.is_file(), f"Music file public/{music['src']} is present.")
        except ValueError as error:
            check('MUSIC_PATH_UNSAFE', str(error), 'inputs.json.props.music.src')
    elif catalog.get('music', {}).get('required'):
        check('MUSIC_REQUIRED', 'This template is cut to music; set music.src to a track with a beat map.',
              'inputs.json.props.music.src')
    schema_checked = input_schema_checks(project, template, props, checks)
    # Files the template itself plays (a second track, sound effects) even though inputs do not name them.
    for record in download_records(project):
        if template in (record.get('templates') or []):
            relative = download_path(record)
            try:
                present = safe_public_path(project, relative).is_file()
            except ValueError:
                present = False
            if not present:
                checks.append({'code': 'TEMPLATE_DOWNLOAD_PENDING', 'status': 'pending', 'location': f'public/{relative}',
                               'message': f'{relative} is download-only and used by {template}; run npm run music in the project.'})
    statuses = {c['status'] for c in checks}
    return concise({'status': 'failed' if 'failed' in statuses else 'pending' if 'pending' in statuses else 'passed',
                    'scope': ['project-format', 'photo-decode', 'photo-slots', 'local-paths'] +
                             (['input-schema'] if schema_checked else []),
                    'notChecked': ([] if schema_checked else ['input-schema']) +
                                  ['creative-accuracy', 'layout', 'motion', 'audio-decode', 'full-render'],
                    'checks': checks}, verbose)


def schema_description(schema, path):
    """The description zod attached to the property at a '$.a.b[0]' path, if any."""
    node = schema
    for part in re.findall(r'\.([^.\[]+)', path):
        node = (node.get('properties') or {}).get(part) if isinstance(node, dict) else None
        if node is None:
            return None
    return node.get('description') if isinstance(node, dict) else None


def input_schema_checks(project, template, props, checks):
    """Check props against the template's JSON Schema (generated from the renderer's zod schema).
    Photos are left to the catalog slot checks, which also know per-format slots. Returns whether it ran."""
    import vvv_schema
    path = next((p for p in (project / PROPS_SCHEMA, project / 'schema' / f'{template}.json') if p.is_file()), None)
    if path is None:
        return False
    try:
        schema = read_json(path)
        if not isinstance(schema, dict):
            raise ValueError('Expected a JSON Schema object.')
    except (OSError, ValueError) as error:
        checks.append({'code': 'INPUT_SCHEMA_UNREADABLE', 'status': 'failed', 'message': str(error),
                       'location': path.relative_to(project).as_posix()})
        return False
    # The renderer merges the template defaults over missing top-level props, so none is required here.
    reduced = dict(schema, properties={k: v for k, v in (schema.get('properties') or {}).items() if k != 'photos'},
                   required=[])
    covered = [c['location'] for c in checks if c['status'] == 'failed']
    found = []
    for where, message in vvv_schema.issues({k: v for k, v in props.items() if k != 'photos'}, reduced):
        location = 'inputs.json.props' + where[1:]
        if any(location == c or location.startswith(c + '.') or location.startswith(c + '[') for c in covered):
            continue  # a dedicated check already reported this field
        hint = schema_description(schema, where)
        found.append({'code': 'INPUT_SCHEMA', 'status': 'failed', 'location': location,
                      'message': f'{message}' + (f' ({hint})' if hint else '') +
                                 f'. See {path.relative_to(project).as_posix()}.'})
    checks.extend(found or [{'code': 'INPUT_SCHEMA', 'status': 'passed', 'location': 'inputs.json.props',
                             'message': 'Inputs match the template props schema.'}])
    checks.extend(unknown_keys(schema, props, path.relative_to(project).as_posix()))
    return True


def unknown_keys(schema, props, schema_name):
    """Keys the props schema does not declare: the renderer's zod schema silently drops them."""
    import vvv_schema
    def resolve(node):
        while isinstance(node, dict) and '$ref' in node:
            node = vvv_schema.pointer(schema, node['$ref'])
        return node if isinstance(node, dict) else {}
    found = []
    def visit(value, node, location):
        node = resolve(node)
        if not isinstance(value, dict) or not isinstance(node.get('properties'), dict) or 'additionalProperties' in node:
            return
        for key in value:
            if key not in node['properties']:
                found.append({'code': 'INPUT_UNKNOWN_KEY', 'status': 'warning', 'location': f'{location}.{key}',
                              'message': f'{schema_name} does not declare {key!r}; the renderer ignores it. '
                                         'Check the spelling against the schema.'})
    root = resolve(schema)
    visit(props, root, 'inputs.json.props')
    for name in ('copy', 'couple', 'music'):
        if isinstance(props.get(name), dict):
            visit(props[name], (root.get('properties') or {}).get(name), f'inputs.json.props.{name}')
    return found


def download_records(project):
    """Download-only files listed in public/music/sources.json (fetched by npm run music)."""
    try:
        sources = read_json(Path(project) / 'public' / 'music' / 'sources.json')
        return [t for t in sources.get('tracks', []) if isinstance(t, dict) and t.get('distribution') == 'download']
    except (OSError, ValueError, AttributeError):
        return []


def download_path(record):
    return f"{record.get('dir', 'music')}/{record.get('file')}"


def download_track(project, src):
    """True when sources.json lists src (e.g. music/x.mp3, sfx/y.wav) as fetched by npm run music."""
    return any(download_path(t) == src for t in download_records(project))


def project_source_files(project):
    """Inventory fingerprinted files without silently omitting linked source or media."""
    project = Path(project)
    files = []

    def walk(path):
        if path.is_symlink():
            relative = path.relative_to(project).as_posix()
            raise ValueError(f'PROJECT_SYMLINK: {relative}: symbolic links are not supported in project source or media.')
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            for child in sorted(path.iterdir()):
                if child.name not in {'.DS_Store', '__pycache__'}:
                    walk(child)

    manifest = project / 'vvv.json'
    if manifest.is_symlink():
        raise ValueError('PROJECT_SYMLINK: vvv.json: symbolic links are not supported in project source or media.')
    for name in FINGERPRINT_PATHS:
        walk(project / name)
    # Ordered by UTF-8 bytes, as render-support.mjs (Buffer.compare) and vvv_package.fingerprint_of order them.
    return sorted(files, key=lambda p: p.relative_to(project).as_posix().encode('utf-8'))


def project_fingerprint(project):
    project = Path(project)
    digest = hashlib.sha256()
    # This definition is shared with scripts/render-support.mjs. Include actual media and source.
    for path in project_source_files(project):
        digest.update(path.relative_to(project).as_posix().encode('utf-8'))
        digest.update(b'\0')
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def safe_output_path(project, relative):
    """Resolve a reported project-local artifact without following symbolic links."""
    if not isinstance(relative, str) or not relative or any(c in relative for c in ('\\', ':', '\0')):
        raise ValueError('Output paths must be project-relative local paths.')
    parts = PurePosixPath(relative)
    if parts.is_absolute() or '..' in parts.parts:
        raise ValueError('Output path escapes the project.')
    path = project
    for part in parts.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('Output paths must not contain symbolic links.')
    if project not in path.resolve().parents:
        raise ValueError('Output path escapes the project.')
    return path


def inspect_output_artifact(project, report):
    """Inspect file presence and size only; neither proves media decoding or review."""
    result = {'status': 'unreported', 'bytes': None, 'sizeChanged': None, 'decode': 'not-checked'}
    if report.get('output') is None:
        return result
    try:
        path = safe_output_path(project, report['output'])
        if not path.exists():
            result['status'] = 'missing'
        elif not path.is_file():
            result['status'] = 'non-file'
        else:
            with path.open('rb') as artifact:
                artifact.read(1)
                result['bytes'] = os.fstat(artifact.fileno()).st_size
            result['status'] = 'present' if result['bytes'] else 'empty'
            expected = report.get('bytes')
            if type(expected) is int and expected >= 0:
                result['sizeChanged'] = result['bytes'] != expected
    except ValueError:
        result['status'] = 'unsafe'
    except OSError:
        result['status'] = 'unreadable'
    return result


def inspect_project(project, verbose=False):
    project = Path(project).expanduser().resolve()
    validation = validate_project(project, verbose)
    if validation['status'] == 'failed':
        return {'status': 'failed', 'validation': validation}
    inputs = read_json(project / 'inputs.json')
    assets = read_json(project / 'assets.json')
    fingerprint = project_fingerprint(project)
    outputs = []
    for path in sorted((project / 'out').glob('*.report.json')):
        try:
            safe_output_path(project, path.relative_to(project).as_posix())
            report = read_json(path)
            if not isinstance(report, dict):
                raise ValueError('Output report must be a JSON object.')
            artifact = inspect_output_artifact(project, report)
            output = {'report': path.relative_to(project).as_posix(), 'mode': report.get('mode'),
                      'status': report.get('status'), 'stale': report.get('fingerprint') != fingerprint,
                      'artifact': artifact}
            for name in ['output', 'compositionId', 'sourceFrameRange', 'sourceTimeRange', 'rangeEnd',
                         'fps', 'width', 'height', 'bytes', 'frames', 'durationSeconds',
                         'encodedDurationSeconds', 'fullDurationSeconds', 'visualReview', 'createdAt']:
                if name in report:
                    output[name] = report[name]
            # This is only a candidate for subsequent decoding and human/Agent review.
            output['deliveryCandidate'] = (output['status'] == 'rendered' and not output['stale'] and
                                           artifact['status'] == 'present' and artifact['sizeChanged'] is False)
            outputs.append(output)
        except (OSError, ValueError):
            outputs.append({'report': path.name, 'status': 'unreadable', 'stale': True,
                            'deliveryCandidate': False})
    return {'status': 'passed', 'template': inputs['template'],
            'format': inputs['props'].get('format', read_json(project / 'catalog' / f"{inputs['template']}.json")['defaultFormat']),
            'assetCount': len(assets['items']), 'fingerprint': fingerprint,
            'workflow': read_json(project / 'vvv.json').get('workflow'), 'outputs': outputs,
            'validation': validation}

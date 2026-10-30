"""Arrange a project's photos along the template's emotional arc, from tags the agent writes after looking.

The agent views the photos (creative/contact-sheet.jpg) and writes creative/photo-tags.json:

    {"photos": {"PHOTO_ID": {"mood": ["funny"], "subject": "groom", "when": "1994", "set": "s2",
                             "slot": "groomKid", "skip": false, "note": "..."}}}

Every field is optional. `arrange` then fills each slot from the section of the arc it belongs to:
pinned photos first, then the best match by subject and mood, keeping photos of one set together where a
slot shows a set, and chronological order where the section asks for it. It writes inputs.json,
creative/arc.json and creative/arc-sheet.jpg, the sheet to show the user before rendering.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re

from vvv_project import (MOODS, SUBJECTS, format_arc, load_catalog, read_json, slot_bounds, slot_takes,
                         validate_project, write_json)

TAGS = 'creative/photo-tags.json'
WHEN = re.compile(r'\d{4}(-\d{2}(-\d{2})?)?')
SET_HINT = re.compile(r'\b(same|one) set\b|grouped by set')
LANDSCAPE = re.compile(r'landscape|full-bleed')
PORTRAIT = re.compile(r'portrait (orientation|shots?|couple)|tall panel|tall and narrow')


def shape(hint):
    """The orientation a slot's hint asks for, if any."""
    return 'landscape' if LANDSCAPE.search(hint or '') else 'portrait' if PORTRAIT.search(hint or '') else None


def read_tags(project, assets, used):
    path = project / TAGS
    if not path.is_file():
        raise ValueError(f'TAGS_MISSING: Write {TAGS} after looking at creative/contact-sheet.jpg; '
                         'see references/story-editing.md.')
    document = read_json(path)
    photos = document.get('photos') if isinstance(document, dict) else None
    if not isinstance(photos, dict):
        raise ValueError(f'TAGS_INVALID: {TAGS} must be {{"photos": {{"PHOTO_ID": {{...}}}}}}.')
    known = {a['id'] for a in assets}
    problems = []
    for photo, tag in photos.items():
        where = f'{TAGS}: {photo}'
        if photo not in known:
            problems.append(f'{where}: not a photo in assets.json')
            continue
        if not isinstance(tag, dict):
            problems.append(f'{where}: expected an object')
            continue
        mood = tag.get('mood', [])
        mood = [mood] if isinstance(mood, str) else mood
        if not isinstance(mood, list) or not all(m in MOODS for m in mood):
            problems.append(f'{where}: mood must be one or more of {", ".join(MOODS)}')
        if 'subject' in tag and tag['subject'] not in SUBJECTS:
            problems.append(f'{where}: subject must be one of {", ".join(SUBJECTS)}')
        if 'when' in tag and not (isinstance(tag['when'], str) and WHEN.fullmatch(tag['when'])):
            problems.append(f'{where}: when must be YYYY, YYYY-MM or YYYY-MM-DD')
        if 'slot' in tag and tag['slot'] not in used:
            problems.append(f'{where}: slot {tag["slot"]!r} is not used by this format')
        if 'set' in tag and not isinstance(tag['set'], str):
            problems.append(f'{where}: set must be a string')
        tag['mood'] = mood if isinstance(mood, list) else []
    if problems:
        raise ValueError('TAGS_INVALID: ' + '; '.join(problems[:12]) + (' …' if len(problems) > 12 else ''))
    return photos


def arc_overrides(project):
    """Section preferences from an applied style preset (creative/style.json, `arc`)."""
    path = project / 'creative' / 'style.json'
    if not path.is_file():
        return {}
    arc = read_json(path).get('arc')
    return arc if isinstance(arc, dict) else {}


def arrange(project, allow_repeat=False):
    project = Path(project).expanduser().resolve()
    inputs = read_json(project / 'inputs.json')
    template, props = inputs.get('template'), inputs.get('props') or {}
    catalog = load_catalog(project, template)
    frame_format = props.get('format') or catalog['defaultFormat']
    arc = format_arc(catalog, frame_format)
    if not arc:
        raise ValueError(f'ARC_MISSING: {template} has no emotional arc in its catalog; place photos by hand.')
    assets = [a for a in (read_json(project / 'assets.json').get('items') or []) if isinstance(a, dict) and a.get('id')]
    used = [e['slot'] for section in arc for e in section['slots']]
    tags = read_tags(project, assets, set(used))
    overrides = arc_overrides(project)
    order = {a['id']: i for i, a in enumerate(assets)}
    orientation = {a['id']: a.get('orientation') for a in assets}
    pool = [a['id'] for a in assets if not tags.get(a['id'], {}).get('skip')]
    if not pool:
        raise ValueError('NO_USABLE_PHOTOS: Every photo is marked skip.')
    slots = catalog['slots']
    shared, take = slot_takes(catalog, len(pool), allow_repeat, frame_format)
    pins = {}
    for photo in pool:
        if tags.get(photo, {}).get('slot'):
            pins.setdefault(tags[photo]['slot'], []).append(photo)
    for name, pinned in pins.items():
        if len(pinned) > slot_bounds(slots[name])[0]:
            raise ValueError(f'TAGS_INVALID: {len(pinned)} photos are pinned to {name}, which holds {slot_bounds(slots[name])[0]}.')

    taken, picks, notes, diagnostics = set(pins_flat(pins)), {}, {}, []

    def preference(section, entry):
        prefer = overrides.get(section['id'], {}) if isinstance(overrides.get(section['id']), dict) else {}
        moods = prefer.get('mood') or entry.get('mood') or section['mood']
        subjects = prefer.get('subject') or entry.get('subject') or []
        return [m for m in moods if m in MOODS], [s for s in subjects if s in SUBJECTS]

    current = {'shape': None}  # the orientation the slot being filled asks for

    def score(photo, moods, subjects):
        tag = tags.get(photo, {})
        subject = 0 if not subjects or tag.get('subject') in subjects else (1 if 'subject' not in tag else 2)
        crop = int(bool(current['shape']) and orientation.get(photo) in ('portrait', 'landscape')
                   and orientation[photo] != current['shape'])
        ranks = [moods.index(m) for m in tag.get('mood', []) if m in moods]
        mood = min(ranks) if ranks else (len(moods) if not tag.get('mood') else len(moods) + 1)
        return subject, crop, mood, order[photo]

    def choose(count, moods, subjects, one_set, avoid, reuse, exclude=(), other_than=None):
        """Best `count` photos not in `avoid`; with `reuse`, avoided photos may follow, matching ones first."""
        if count <= 0:
            return []
        fresh = [p for p in pool if p not in avoid]
        if reuse:
            def key(p):
                subject, crop, mood, index = score(p, moods, subjects)
                matched = 0 if mood < len(moods) else (1 if mood == len(moods) else 2)
                # A slot that shows sets (a gallery grouped by outfit) prefers photos from a tagged set.
                loose = one_set and any(t.get('set') for t in tags.values()) and not tags.get(p, {}).get('set')
                return subject, matched, loose, crop, p in avoid, mood, index
            ranked = sorted([p for p in pool if p not in exclude], key=key)
        else:
            ranked = sorted(fresh, key=lambda p: score(p, moods, subjects))
        if one_set and count > 1:
            groups = {}
            for photo in ranked:
                if tags.get(photo, {}).get('set'):
                    groups.setdefault(tags[photo]['set'], []).append(photo)
            full = [g for g in groups.values() if len(g) >= count]
            # A second group on the same page shows another outfit when there is one to show.
            if other_than and any(tags[g[0]]['set'] != other_than for g in full):
                full = [g for g in full if tags[g[0]]['set'] != other_than]
            if full:
                best = min(full, key=lambda g: [score(p, moods, subjects) for p in g[:count]])
                return best[:count]
        picked = ranked[:count]
        while allow_repeat and len(picked) < count and pool:
            picked.append(ranked[len(picked) % len(ranked)] if ranked else pool[0])
        return picked

    def arrange_slot(section, entry, count, independent):
        name = entry['slot']
        moods, subjects = preference(section, entry)
        current['shape'] = shape(slots[name].get('hint'))
        one_set = bool(SET_HINT.search(slots[name].get('hint', '')))
        chosen = list(pins.get(name, []))
        groups = slots[name].get('groups')
        if groups and not chosen and sum(groups) == count:
            # One outfit per group (a pair, a row of columns); consecutive groups change outfit when they can.
            previous = None
            for size in groups:
                part = choose(size, moods, subjects, True, taken | set(chosen), independent or allow_repeat,
                              exclude=set(chosen), other_than=previous)
                previous = tags.get(part[0], {}).get('set') if part else None
                chosen += part
        else:
            chosen += choose(count - len(chosen), moods, subjects, one_set, taken | set(chosen),
                             independent or allow_repeat, exclude=set(chosen))
        if independent:
            # A gallery shows sets (outfits) together, in the order the user's photos first show them.
            first = {}
            for photo in sorted(chosen, key=order.get):
                first.setdefault(tags.get(photo, {}).get('set'), order[photo])
            chosen.sort(key=lambda p: (first[tags.get(p, {}).get('set')], tags.get(p, {}).get('when', '9999'), order[p]))
        elif section.get('order') == 'chronological':
            chosen.sort(key=lambda p: (tags.get(p, {}).get('when', '9999'), order[p]))
        picks[name] = chosen
        taken.update(chosen)
        for photo in chosen:
            subject, crop, mood, _ = score(photo, moods, subjects)
            if crop and photo not in pins.get(name, []):
                diagnostics.append({'code': 'ARC_CROP', 'severity': 'info', 'location': f'props.photos.{name}',
                                    'message': f'{photo} is {orientation[photo]} in a {current["shape"]} slot; check the crop.'})
            if photo in pins.get(name, []):
                notes[(name, photo)] = 'pinned'
            elif subject == 2 or mood == len(moods) + 1:
                notes[(name, photo)] = 'mismatch'
                diagnostics.append({'code': 'ARC_MISMATCH', 'severity': 'warning', 'location': f'props.photos.{name}',
                                    'message': f'{photo} does not match {name} ({"/".join(subjects or moods)}); '
                                               'there were not enough better photos. Confirm with the user or pin another.'})
            elif photo not in tags:
                notes[(name, photo)] = 'untagged'
            else:
                notes[(name, photo)] = 'match'
        if entry.get('pin') and not pins.get(name):
            diagnostics.append({'code': 'ARC_UNPINNED', 'severity': 'info', 'location': f'props.photos.{name}',
                                'message': f'{name} shows something specific ({slots[name].get("hint", name)}); '
                                           'pin a photo to it with "slot" in the tags.'})

    sections = [(s, e) for s in arc for e in s['slots']]
    # Named moments (slots that ask for a subject: the opening, portraits, proposal, ending) choose first, then
    # the other shared slots in film order, then the galleries; so the close never gets only the leftovers.
    named = [(s, e) for s, e in sections if e.get('subject') and e['slot'] in take]
    for section, entry in named + [(s, e) for s, e in sections if (s, e) not in named]:
        if entry['slot'] in take:
            arrange_slot(section, entry, max(take[entry['slot']], len(pins.get(entry['slot'], []))), False)
    for section, entry in sections:
        if entry['slot'] not in take:
            arrange_slot(section, entry, slot_bounds(slots[entry['slot']])[0], True)

    photos = deepcopy(props.get('photos') or {})
    for name, chosen in picks.items():
        kind = slots[name]['kind']
        photos[name] = (chosen[0] if chosen else '') if kind == 'single' else (
            ' '.join('@' + p for p in chosen) if kind == 'tokens' else chosen)
    untagged = [p for p in pool if p not in tags]
    if untagged:
        diagnostics.append({'code': 'PHOTOS_UNTAGGED', 'severity': 'info', 'location': TAGS,
                            'message': f'{len(untagged)} photos have no tags and were placed by input order only.'})
    unused = [p for p in pool if p not in taken]
    record = {'template': template, 'format': frame_format, 'sections': [
        {'id': s['id'], 'mood': preference(s, {})[0], 'slots': [
            {'slot': e['slot'], 'photos': [{'id': p, 'match': notes.get((e['slot'], p), 'match'),
                                            **{k: tags[p][k] for k in ('mood', 'subject', 'when', 'set') if tags.get(p, {}).get(k)}}
                                           for p in picks.get(e['slot'], [])]} for e in s['slots']]} for s in arc],
        'unused': unused, 'diagnostics': diagnostics}

    previous = (project / 'inputs.json').read_bytes()
    write_json(project / 'inputs.json', {**inputs, 'props': {**props, 'photos': photos}})
    validation = validate_project(project)
    if validation['status'] == 'failed':
        (project / 'inputs.json').write_bytes(previous)
        raise ValueError('ARRANGE_INVALID: ' + '; '.join(c['code'] + ': ' + c['message'] for c in validation['checks']
                                                          if c['status'] == 'failed'))
    write_json(project / 'creative' / 'arc.json', record)
    arc_sheet(project, record, {a['id']: a for a in assets}, project / 'creative' / 'arc-sheet.jpg')
    return {'status': 'arranged', 'template': template, 'format': frame_format,
            'sections': [{'id': s['id'], 'mood': s['mood'],
                          'photos': [p['id'] for slot in s['slots'] for p in slot['photos']]} for s in record['sections']],
            'unused': len(unused), 'diagnostics': diagnostics, 'sheet': 'creative/arc-sheet.jpg',
            'next': {'action': 'ask_user',
                     'say': 'Here is the order of your photos, section by section (creative/arc-sheet.jpg). '
                            'Does the emotional flow look right before I render a sample?'}}


def pins_flat(pins):
    return [p for pinned in pins.values() for p in pinned]


def arc_sheet(project, record, assets, destination):
    """One row band per section: its mood, then each photo with its slot, so the user can confirm the order."""
    from PIL import Image, ImageDraw
    cell_w, cell_h, header, columns = 220, 190, 34, 8
    bands = []
    for index, section in enumerate(record['sections'], 1):
        tiles = [(slot['slot'], p['id'], p['match']) for slot in section['slots'] for p in slot['photos']]
        bands.append((f"{index}. {section['id']}  ({', '.join(section['mood'])})", tiles))
    height = sum(header + max(1, (len(t) + columns - 1) // columns) * cell_h for _, t in bands)
    sheet = Image.new('RGB', (columns * cell_w, max(1, height)), '#f4f2ec')
    draw = ImageDraw.Draw(sheet)
    y = 0
    for title, tiles in bands:
        draw.rectangle((0, y, sheet.width, y + header - 4), fill='#1e1e1e')
        draw.text((10, y + 10), title, fill='#f5f3e8')
        y += header
        for k, (slot, photo, match) in enumerate(tiles):
            x, top = (k % columns) * cell_w, y + (k // columns) * cell_h
            item = assets.get(photo)
            if item:
                with Image.open(project / 'public' / item['file']) as source:
                    tile = source.convert('RGB')
                    tile.thumbnail((cell_w - 14, cell_h - 34))
                    sheet.paste(tile, (x + (cell_w - tile.width) // 2, top + 4))
            draw.text((x + 6, top + cell_h - 26), f'{slot}: {photo}'[:34], fill='#b00020' if match == 'mismatch' else '#222222')
        y += max(1, (len(tiles) + columns - 1) // columns) * cell_h
    sheet.save(destination, quality=86)

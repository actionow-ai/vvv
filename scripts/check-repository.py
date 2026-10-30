#!/usr/bin/env python3
"""Check the Git publication candidate without reading ignored local material.

Only local Markdown destinations are checked; remote URLs and heading anchors are
not fetched or validated. --portable also copies just the skill's publishable
files and runs CLI/import smoke checks without image generation or authentication.
"""
import argparse
import ast
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlsplit


SKILL = Path('skills/vvv')
REQUIRED = (
    'README.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'CONTRIBUTING.md',
    'SECURITY.md', 'requirements.txt', 'skills/vvv/SKILL.md',
    'skills/vvv/requirements.txt', 'skills/vvv/LICENSE', 'skills/vvv/scripts/vvv.py',
    'skills/vvv/scripts/vvv_image.py', 'skills/vvv/scripts/vvv_image_c2c.py',
    'skills/vvv/scripts/vvv_media.py',
    'skills/vvv/vendor/c2c_img/UPSTREAM.json',
    'kits/remotion/package.json', 'kits/remotion/package-lock.json',
)
# Required once the kit ships templates (a catalog), since it then ships media and release notes.
KIT_REQUIRED = ('MEDIA_LICENSE.md', 'CHANGELOG.md', 'kits/remotion/LICENSE')
KIT_CATALOG = Path('kits/remotion/catalog')
PRIVATE_PREFIXES = (
    '.work/', '.superpowers/', 'vvv-skill/', 'docs/research/', 'docs/plans/',
    'docs/proposals/', 'plans/', 'proposals/',
)
PRIVATE_PARTS = {'.venv', 'node_modules', '__pycache__', '.DS_Store', 'out', 'build'}
# Client material never belongs in the repository, whatever the folder depth.
CLIENT_PARTS = {'customer', 'customers'}
# Download-only music: fetched into projects by `npm run music`, never redistributed.
DOWNLOAD_ONLY = ('kits/remotion/public/music/mixkit-', 'kits/remotion/public/sfx/mixkit-')
# Maintainer-local denylist (ignored by Git): one case-insensitive term per line, such as client
# names or project codes. It keeps those names out of this public script.
PRIVATE_TERMS_FILE = '.private-terms'
TEXT_SUFFIXES = {'.md', '.json', '.ts', '.tsx', '.mjs', '.cjs', '.js', '.py', '.txt', '.yml', '.yaml',
                 '.toml', '.css', '.html', '.svg', '.sh'}


def publication_files(root):
    result = subprocess.run(
        ['git', '-C', str(root), 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
        check=True, capture_output=True,
    )
    return {Path(os.fsdecode(name)) for name in result.stdout.split(b'\0') if name}


def private_terms(root):
    path = root / PRIVATE_TERMS_FILE
    if not path.is_file():
        return []
    lines = path.read_text(encoding='utf-8').splitlines()
    return [line.strip().lower() for line in lines if line.strip() and not line.lstrip().startswith('#')]


def check_private_material(root, candidates, errors):
    """Reject client folders, download-only music and maintainer-listed private terms."""
    terms = private_terms(root)
    for relative in sorted(candidates):
        name = relative.as_posix()
        if CLIENT_PARTS.intersection(part.lower() for part in relative.parts):
            errors.append('%s: client material is in the publication candidate' % relative)
        if name.startswith(DOWNLOAD_ONLY) and relative.suffix.lower() in {'.mp3', '.wav', '.ogg', '.m4a'}:
            errors.append('%s: download-only music must not be published; it is fetched by npm run music' % relative)
        if not terms:
            continue
        lowered = name.lower()
        hit = next((t for t in terms if t in lowered), None)
        if hit is None and relative.suffix.lower() in TEXT_SUFFIXES:
            text = (root / relative).read_text(encoding='utf-8', errors='ignore').lower()
            hit = next((t for t in terms if t in text), None)
        if hit is not None:
            # Do not echo the term itself: the output may be shared.
            errors.append('%s: contains a term from %s' % (relative, PRIVATE_TERMS_FILE))


def markdown_destinations(content):
    """Read inline links/images, reference definitions, and HTML src/href values."""
    lines = []
    fence = None
    for line in content.splitlines():
        match = re.match(r'^\s{0,3}(`{3,}|~{3,})', line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            continue
        if fence is None:
            lines.append(line)
    content = '\n'.join(lines)
    content = re.sub(r'<!--.*?-->', '', content, flags=re.S)
    content = re.sub(r'(`+).*?\1', '', content)
    destination = r'(?:<([^>\n]+)>|([^\s)]+))'
    for match in re.finditer(r'!?\[[^\]\n]*\]\(\s*' + destination, content):
        yield match.group(1) or match.group(2)
    for match in re.finditer(r'^\s{0,3}\[[^\]\n]+\]:\s*' + destination, content, re.M):
        yield match.group(1) or match.group(2)
    for match in re.finditer(r'\b(?:src|href)\s*=\s*([\'"])(.*?)\1', content, re.I):
        yield html.unescape(match.group(2))


def check_links(root, candidates, errors):
    count = 0
    for relative in sorted(candidates):
        if relative.suffix.lower() != '.md' or not (root / relative).is_file():
            continue
        count += 1
        for destination in markdown_destinations((root / relative).read_text(encoding='utf-8')):
            parsed = urlsplit(destination)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            path = unquote(parsed.path)
            bound = root / SKILL if SKILL in relative.parents else root
            target = (root / relative.parent / path).resolve()
            if not target.is_relative_to(bound):
                errors.append('%s: local link escapes %s: %s' % (relative, bound.relative_to(root) or '.', destination))
                continue
            published = target.relative_to(root)
            available = published in candidates if target.is_file() else (
                target.is_dir() and any(published in item.parents for item in candidates)
            )
            if not available:
                errors.append('%s: missing or unpublished local target: %s' % (relative, destination))
    return count


def check_skill(root, candidates, errors):
    path = root / SKILL / 'SKILL.md'
    if not path.is_file():
        return
    content = path.read_text(encoding='utf-8')
    header = re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)', content, re.S)
    fields = {}
    if header:
        # The package uses simple, one-line scalars; no YAML dependency is needed.
        for line in header.group(1).splitlines():
            key, separator, value = line.partition(':')
            if separator:
                fields[key.strip()] = value.strip().strip('\'"')
    if fields.get('name') != 'vvv' or not fields.get('description') or fields.get('description') in {'>', '|'}:
        errors.append('skills/vvv/SKILL.md: expected name: vvv and a nonempty, one-line description')
    for relative in candidates:
        if SKILL in relative.parents and (root / relative).is_symlink():
            errors.append('%s: skill files must be regular files for portable installation' % relative)


def check_vendor(root, candidates, errors):
    vendor = SKILL / 'vendor/c2c_img'
    manifest = root / vendor / 'UPSTREAM.json'
    adapter = SKILL / 'scripts/vvv_image_c2c.py'
    if not manifest.is_file() or not (root / adapter).is_file():
        return
    try:
        upstream = json.loads(manifest.read_text(encoding='utf-8'))
        hashes = upstream['sha256']
        if not isinstance(hashes, dict) or not {'c2c_img.py', 'LICENSE'}.issubset(hashes):
            raise ValueError('expected hashes for c2c_img.py and LICENSE')
        if not re.fullmatch(r'[0-9a-f]{40}', upstream['commit']):
            raise ValueError('expected a full upstream commit SHA')
        for name, expected in hashes.items():
            target = (root / vendor / name).resolve()
            if not target.is_relative_to(root / vendor) or target.relative_to(root) not in candidates:
                errors.append('%s: vendor target is outside the published package: %s' % (manifest.relative_to(root), name))
            elif not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != expected:
                errors.append('%s: vendor SHA-256 mismatch' % (vendor / name))
        pins = {}
        for statement in ast.parse((root / adapter).read_text(encoding='utf-8')).body:
            if isinstance(statement, ast.Assign):
                for target in statement.targets:
                    if isinstance(target, ast.Name) and target.id.startswith('UPSTREAM_'):
                        pins[target.id] = ast.literal_eval(statement.value)
        expected_pins = {'UPSTREAM_SHA256': hashes['c2c_img.py'],
                         'UPSTREAM_COMMIT': upstream['commit'], 'UPSTREAM_VERSION': upstream['version']}
        if any(pins.get(key) != value for key, value in expected_pins.items()):
            errors.append('%s: adapter pins do not match vendor UPSTREAM.json' % adapter)
    except (KeyError, TypeError, ValueError, SyntaxError, OSError) as error:
        errors.append('%s: invalid vendor metadata: %s' % (manifest.relative_to(root), error))


def check_vendored_folders(root, candidates, errors):
    """Every other vendor folder: each file listed in its UPSTREAM.json and unchanged, nothing unlisted."""
    for manifest in sorted((root / SKILL / 'vendor').glob('*/UPSTREAM.json')):
        folder = manifest.parent
        if folder.name == 'c2c_img':
            continue
        try:
            upstream = json.loads(manifest.read_text(encoding='utf-8'))
            if not re.fullmatch(r'[0-9a-f]{40}', upstream['commit']):
                raise ValueError('expected a full upstream commit SHA')
            hashes = upstream['sha256']
            present = {p.relative_to(folder).as_posix() for p in folder.rglob('*')
                       if p.is_file() and p.name != 'UPSTREAM.json' and p.relative_to(root) in candidates}
            for name in sorted(present - set(hashes)):
                errors.append('%s: file not recorded in UPSTREAM.json' % (folder / name).relative_to(root))
            for name, expected in hashes.items():
                target = folder / name
                if name not in present:
                    errors.append('%s: recorded vendor file is missing' % target.relative_to(root))
                elif hashlib.sha256(target.read_bytes()).hexdigest() != expected:
                    errors.append('%s: vendor SHA-256 mismatch' % target.relative_to(root))
        except (KeyError, TypeError, ValueError, OSError) as error:
            errors.append('%s: invalid vendor metadata: %s' % (manifest.relative_to(root), error))


def check_portable(root, candidates):
    with tempfile.TemporaryDirectory(prefix='vvv-portable-') as directory:
        destination = Path(directory) / 'vvv'
        for relative in sorted(candidates):
            if SKILL in relative.parents:
                target = destination / relative.relative_to(SKILL)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(root / relative, target)
        environment = os.environ.copy()
        environment.pop('PYTHONPATH', None)
        environment.pop('PYTHONHOME', None)
        commands = [
            [sys.executable, str(destination / 'scripts' / name), '--help']
            for name in ('vvv.py', 'vvv_image.py', 'vvv_media.py')
        ]
        commands.append([sys.executable, '-c',
                         'import sys; sys.path.insert(0, "scripts"); '
                         'import vvv_image_c2c; vvv_image_c2c._load_upstream()'])
        for command in commands:
            result = subprocess.run(command, cwd=destination, env=environment,
                                    capture_output=True, text=True, timeout=30)
            if result.returncode:
                raise ValueError('copied skill smoke check failed: %s' % (result.stderr or result.stdout).strip())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--portable', action='store_true', help='also smoke-test a standalone copy of the skill')
    args = parser.parse_args()
    root = args.root.resolve()
    errors = []
    try:
        candidates = publication_files(root)
        required = REQUIRED
        if any(KIT_CATALOG in path.parents for path in candidates):
            required += KIT_REQUIRED
        for name in required:
            if Path(name) not in candidates or not (root / name).is_file():
                errors.append('%s: required publication file is missing' % name)
        for relative in sorted(candidates):
            if relative.as_posix().startswith(PRIVATE_PREFIXES) or PRIVATE_PARTS.intersection(relative.parts):
                errors.append('%s: private or generated material is in the publication candidate' % relative)
            if not (root / relative).is_file():
                errors.append('%s: publication candidate is not an available regular file' % relative)
            elif not (root / relative).resolve().is_relative_to(root):
                errors.append('%s: publication file points outside the repository' % relative)
        # Reject unsafe publication paths before reading any candidate contents.
        if not errors:
            check_private_material(root, candidates, errors)
        if not errors:
            documents = check_links(root, candidates, errors)
            check_skill(root, candidates, errors)
            check_vendor(root, candidates, errors)
            check_vendored_folders(root, candidates, errors)
        if not errors and args.portable:
            check_portable(root, candidates)
    except (OSError, UnicodeError, ValueError, subprocess.SubprocessError) as error:
        errors.append(str(error))
    if errors:
        for error in errors:
            print('FAIL: ' + error, file=sys.stderr)
        return 1
    print('PASS: %s publication files; %s Markdown files; skill references, frontmatter, and vendor integrity' % (len(candidates), documents))
    if args.portable:
        print('PASS: copied skill CLI and vendored import checks (no generation or login)')
    return 0


if __name__ == '__main__':
    sys.exit(main())

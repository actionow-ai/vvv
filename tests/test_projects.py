from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills' / 'vvv' / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from vvv_project import (bind_photos, create_project, describe_template, input_schema_checks, inspect_project,
                         list_templates, load_catalog, project_fingerprint, validate_project)
from vvv_assets import inventory_images
import vvv_assets


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.photos = self.base / 'photos'
        self.photos.mkdir()
        self.kit = self.base / 'kit'
        (self.kit / 'catalog').mkdir(parents=True)
        (self.kit / 'src').mkdir()
        (self.kit / 'public' / 'photos').mkdir(parents=True)
        (self.kit / 'src' / 'index.tsx').write_text('export const source = true;')
        (self.kit / 'public' / 'photos' / 'old-demo.jpg').write_text('must not copy')
        (self.kit / 'package.json').write_text('{"private":true}')
        self.catalog = {
            'id': 'doodle', 'compositionId': 'VVV-Doodle',
            'defaultProps': {'copy': {'title': 'Example'}, 'fps': 30,
                             'music': {'src': ''}, 'photos': {}},
            'slots': {'cover': {'kind': 'single', 'count': 1},
                      'pair': {'kind': 'array', 'count': 2, 'min': 2}},
            'sample': {'from': 1, 'to': 3},
            'formats': {'16:9': {'width': 1920, 'height': 1080}, '9:16': {'width': 1080, 'height': 1920}},
            'defaultFormat': '16:9',
        }
        self.write_catalog()

    def write_catalog(self):
        (self.kit / 'catalog' / 'doodle.json').write_text(json.dumps(self.catalog))

    def photo(self, name, color='red', size=(64, 96)):
        path = self.photos / name
        Image.new('RGB', size, color).save(path)
        return path

    def make_project(self, allow_repeat=False):
        return create_project(self.kit, 'doodle', [self.photos], self.base / 'project',
                              allow_repeat=allow_repeat)

    def populated(self):
        self.photo('a.png', 'red')
        self.photo('b.png', 'green')
        self.photo('c.png', 'blue')
        self.make_project()
        return self.base / 'project'

    def test_explicit_order_and_duplicate_content(self):
        a = self.photo('a.png', 'red')
        b = self.photo('b.png', 'green')
        clone = self.photos / 'clone.png'
        clone.write_bytes(a.read_bytes())
        items, diagnostics = inventory_images([b, a, clone])
        self.assertEqual([p['name'] for p in items], ['b.png', 'a.png'])
        self.assertTrue(any(d['code'] == 'DUPLICATE_CONTENT' for d in diagnostics))

    def test_bad_image_and_symlink_are_reported(self):
        self.photo('a.png')
        (self.photos / 'broken.jpg').write_text('not an image')
        secret = self.base / 'outside.png'
        Image.new('RGB', (20, 20), 'white').save(secret)
        (self.photos / 'outside.png').symlink_to(secret)
        items, diagnostics = inventory_images([self.photos])
        self.assertEqual(len(items), 1)
        self.assertIn('UNREADABLE_IMAGE', {d['code'] for d in diagnostics})
        self.assertIn('SYMLINK_SKIPPED', {d['code'] for d in diagnostics})

    def test_orientation_is_normalized(self):
        image = Image.new('RGB', (80, 40), 'red')
        exif = Image.Exif()
        exif[274] = 6
        image.save(self.photos / 'rotated.jpg', exif=exif)
        self.make_project(allow_repeat=True)
        project = self.base / 'project'
        asset = json.loads((project / 'assets.json').read_text())['items'][0]
        self.assertEqual((asset['width'], asset['height']), (40, 80))
        with Image.open(project / 'public' / asset['file']) as normalized:
            self.assertEqual(normalized.size, (40, 80))
            self.assertNotIn(274, normalized.getexif())

    def test_insufficient_photos_do_not_create_project(self):
        self.photo('one.png')
        with self.assertRaisesRegex(ValueError, 'INSUFFICIENT_PHOTOS'):
            self.make_project()
        self.assertFalse((self.base / 'project').exists())

    def test_explicit_reuse_is_recorded(self):
        self.photo('one.png')
        result = self.make_project(allow_repeat=True)
        self.assertTrue(any(d['code'] == 'PHOTO_REUSED' for d in result['diagnostics']))
        self.assertEqual(validate_project(self.base / 'project')['status'], 'passed')

    def test_existing_destination_is_untouched(self):
        target = self.base / 'project'
        target.mkdir()
        sentinel = target / 'keep.txt'
        sentinel.write_text('user content')
        with self.assertRaisesRegex(ValueError, 'DESTINATION_EXISTS'):
            self.make_project()
        self.assertEqual(sentinel.read_text(), 'user content')

    def test_project_is_portable_and_contains_no_old_demo(self):
        original = self.populated()
        self.assertFalse((original / 'public' / 'photos' / 'old-demo.jpg').exists())
        moved = self.base / 'moved'
        original.rename(moved)
        self.assertEqual(validate_project(moved)['status'], 'passed')
        report = inspect_project(moved)
        self.assertEqual(report['template'], 'doodle')
        self.assertEqual(report['assetCount'], 3)
        for name in ['vvv.json', 'assets.json', 'inputs.json', 'PROJECT.md']:
            self.assertNotIn(str(self.base), (moved / name).read_text())

    def test_initialized_project_retains_kit_license_and_media_notices(self):
        notices = {
            'LICENSE': 'MIT License\nCopyright (c) 2026 Vibe Vision Video contributors\n',
            'MEDIA_LICENSE.md': '[License](LICENSE)\n',
            'THIRD_PARTY_NOTICES.md': '[Media](MEDIA_LICENSE.md)\n',
            'ASSETS.md': '[Notices](THIRD_PARTY_NOTICES.md)\n',
        }
        for name, text in notices.items():
            (self.kit / name).write_text(text)
        project = self.populated()
        for name, text in notices.items():
            self.assertTrue((project / name).is_file(), name)
            self.assertEqual((project / name).read_text(), text)

    def test_missing_asset_and_path_escape_are_diagnostics(self):
        project = self.populated()
        assets = json.loads((project / 'assets.json').read_text())
        assets['items'][0]['file'] = '../outside.png'
        assets['items'][1]['file'] = 'photos/missing.png'
        (project / 'assets.json').write_text(json.dumps(assets))
        result = validate_project(project)
        self.assertEqual(result['status'], 'failed')
        codes = {x['code'] for x in result['checks']}
        self.assertIn('ASSET_PATH_UNSAFE', codes)
        self.assertIn('ASSET_MISSING', codes)

    def test_unknown_photo_and_array_underflow_fail(self):
        project = self.populated()
        inputs = json.loads((project / 'inputs.json').read_text())
        inputs['props']['photos'] = {'cover': 'not-in-project', 'pair': []}
        (project / 'inputs.json').write_text(json.dumps(inputs))
        codes = {c['code'] for c in validate_project(project)['checks']}
        self.assertIn('UNKNOWN_PHOTO_ID', codes)
        self.assertIn('SLOT_COUNT', codes)

    def test_unknown_protocol_version_fails(self):
        project = self.populated()
        manifest = json.loads((project / 'vvv.json').read_text())
        manifest['vvvFormat'] = '99.0'
        (project / 'vvv.json').write_text(json.dumps(manifest))
        codes = {c['code'] for c in validate_project(project)['checks']}
        self.assertIn('UNSUPPORTED_VERSION', codes)

    def test_independent_gallery_reuses_without_needing_extra_unique_photos(self):
        self.catalog['slots']['gallery'] = {'kind': 'array', 'count': 37, 'min': 1,
                                             'independent': True, 'max': 37}
        self.write_catalog()
        project = self.populated()
        props = json.loads((project / 'inputs.json').read_text())['props']
        self.assertEqual(len(props['photos']['gallery']), 3)
        self.assertEqual(validate_project(project)['status'], 'passed')

    def test_stale_render_report_after_source_change(self):
        project = self.populated()
        current = inspect_project(project)['fingerprint']
        (project / 'out').mkdir()
        (project / 'out' / 'sample.report.json').write_text(json.dumps({
            'status': 'rendered', 'fingerprint': current, 'mode': 'sample'}))
        self.assertFalse(inspect_project(project)['outputs'][0]['stale'])
        (project / 'src' / 'index.tsx').write_text('export const source = false;')
        self.assertTrue(inspect_project(project)['outputs'][0]['stale'])

    def run_cli(self, command, project, *extra):
        return subprocess.run([sys.executable, str(SCRIPTS / 'vvv.py'), command,
                               '--project', str(project), *extra], capture_output=True, text=True)

    def vvv(self, *arguments):
        result = subprocess.run([sys.executable, str(SCRIPTS / 'vvv.py'), *arguments], capture_output=True, text=True)
        return result.returncode, json.loads(result.stdout)

    def test_validate_lists_only_checks_that_did_not_pass_unless_verbose(self):
        project = self.populated()
        code, report = self.vvv('validate', '--project', str(project))
        self.assertEqual((code, report['status'], report['checks']), (0, 'passed', []))
        self.assertGreater(report['passed'], 5)
        code, verbose = self.vvv('validate', '--project', str(project), '--verbose')
        self.assertEqual(len(verbose['checks']), verbose['passed'])
        messages = {c['code']: c['message'] for c in verbose['checks']}
        self.assertEqual(messages['FPS'], 'fps 30 is supported.')
        self.assertEqual(messages['FORMAT'], 'Format 16:9 is supported.')
        self.assertNotIn('must', ' '.join(messages.values()))
        code, inspected = self.vvv('inspect', '--project', str(project))
        self.assertEqual(inspected['validation']['checks'], [])
        code, inspected = self.vvv('inspect', '--project', str(project), '--verbose')
        self.assertTrue(inspected['validation']['checks'])

    def test_inspect_stays_small_for_a_hundred_photos(self):
        self.catalog['slots']['pair'] = {'kind': 'array', 'count': 99, 'min': 2}
        self.write_catalog()
        for index in range(100):
            self.photo(f'{index:03d}.png', (index, 2 * index, 255 - index), (8, 8))
        self.make_project()
        result = self.run_cli('inspect', self.base / 'project')
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertLess(len(result.stdout.encode('utf-8')), 1500, result.stdout)

    def test_failures_share_one_shape(self):
        self.photo('a.png')
        cases = [(['templates', '--kit', str(self.base / 'nowhere')], 'KIT_NOT_FOUND', 1),
                 (['init', '--kit', str(self.base / 'nowhere'), '--template', 'doodle', '--photos', str(self.photos),
                   '--output', str(self.base / 'x')], 'KIT_NOT_FOUND', 1),
                 (['init', '--kit', str(self.kit), '--template', 'missing', '--photos', str(self.photos),
                   '--output', str(self.base / 'x')], 'UNKNOWN_TEMPLATE', 1),
                 (['init', '--kit', str(self.kit), '--template', 'doodle', '--photos', str(self.photos), '--example',
                   '--output', str(self.base / 'x')], 'INVALID_ARGUMENTS', 2),
                 (['sample', '--project', str(self.base), '--scale', '3'], 'INVALID_ARGUMENTS', 2),
                 (['render', '--project', str(self.base), '--scale', '0'], 'INVALID_ARGUMENTS', 2),
                 (['validate', '--project', str(self.base / 'nowhere')], 'VALIDATION_FAILED', 1),
                 (['describe', '--template', 'missing'], 'UNKNOWN_TEMPLATE', 1),  # bundled kit; KIT_REQUIRED is tested separately
                 (['describe', '--kit', str(self.kit), '--template', 'doodle', '--format', '1:1'], 'UNSUPPORTED_FORMAT', 1)]
        for arguments, expected, status in cases:
            with self.subTest(arguments=arguments):
                result = subprocess.run([sys.executable, str(SCRIPTS / 'vvv.py'), *arguments], capture_output=True, text=True)
                report = json.loads(result.stdout)
                self.assertEqual((result.returncode, report['status'], report['code']), (status, 'failed', expected))
                self.assertTrue(report['message'])
                self.assertFalse(report['message'].startswith(expected + ':'))
                self.assertFalse((self.base / 'x').exists())

    def test_unexpected_exceptions_and_media_errors_still_print_json(self):
        import contextlib, io, os
        from unittest.mock import patch
        import vvv
        from vvv_media import MediaError
        for target, error, expected in [('vvv_project.list_templates', AttributeError('boom'), 'INTERNAL_ERROR'),
                                        ('vvv_project.list_templates', MediaError('tool_missing', 'no ffmpeg'), 'TOOL_MISSING'),
                                        ('vvv_project.list_templates', OSError(13, 'Permission denied', 'x.json'), 'FILE_ERROR')]:
            with self.subTest(expected=expected), patch(target, side_effect=error), \
                    patch.dict(os.environ, {'VVV_DEBUG': ''}):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    status = vvv.main(['templates', '--kit', str(self.kit)])
                report = json.loads(output.getvalue())
                self.assertEqual((status, report['status'], report['code']), (1, 'failed', expected))

    def test_kit_defaults_to_vvv_kit_then_the_bundled_kit(self):
        import contextlib, io, os
        from unittest.mock import patch
        import vvv
        with patch.dict(os.environ, {'VVV_KIT': str(self.kit)}):
            code, report = self.vvv('templates')
        self.assertEqual((code, [t['id'] for t in report['templates']]), (0, ['doodle']))
        with patch.dict(os.environ, {'VVV_KIT': ''}):
            code, report = self.vvv('templates')  # this checkout's kits/remotion, beside the skill
        self.assertIn('album', [t['id'] for t in report['templates']])
        output = io.StringIO()
        with patch.dict(os.environ, {'VVV_KIT': ''}), patch('vvv.default_kit', return_value=None), \
                contextlib.redirect_stdout(output):
            status = vvv.main(['describe', '--template', 'doodle'])
        report = json.loads(output.getvalue())
        self.assertEqual((status, report['code']), (1, 'KIT_REQUIRED'))
        self.assertIn('VVV_KIT', report['message'])

    def test_failures_tell_the_agent_what_to_do_next(self):
        project = self.populated()
        cases = [(['init', '--kit', str(self.kit), '--template', 'missing', '--photos', str(self.photos),
                   '--output', str(self.base / 'x')], 'UNKNOWN_TEMPLATE', 'run'),
                 (['init', '--kit', str(self.kit)], 'INVALID_ARGUMENTS', 'run'),
                 (['templates', '--kit', str(self.base / 'nowhere')], 'KIT_NOT_FOUND', 'run'),
                 (['sample', '--project', str(project)], 'DEPENDENCIES_MISSING', 'run')]
        for arguments, code, action in cases:
            with self.subTest(arguments=arguments):
                _, report = self.vvv(*arguments)
                self.assertEqual((report['code'], report['next']['action']), (code, action))
        _, report = self.vvv('sample', '--project', str(project))
        self.assertEqual((report['next']['command'], report['next']['cwd']), (['npm', 'ci'], str(project.resolve())))

    def test_doctor_reports_each_gap_with_its_fix(self):
        import contextlib, io
        from unittest.mock import patch
        import vvv
        code, report = self.vvv('doctor', '--kit', str(self.kit))
        self.assertEqual(code, 0 if report['status'] == 'passed' else 1)
        self.assertEqual([c['code'] for c in report['checks']][:2], ['PYTHON', 'PILLOW'])
        self.assertTrue(all('next' in c for c in report['checks'] if c['status'] == 'failed'))
        output = io.StringIO()
        with patch('shutil.which', return_value=None), contextlib.redirect_stdout(output):
            status = vvv.main(['doctor', '--kit', str(self.base / 'nowhere'), '--project', str(self.populated())])
        report = json.loads(output.getvalue())
        failed = {c['code']: c['next'] for c in report['checks'] if c['status'] == 'failed'}
        self.assertEqual(status, 1)
        self.assertEqual(failed['NODE']['action'], 'ask_user')
        self.assertEqual(failed['KIT']['command'][:2], ['git', 'clone'])
        self.assertEqual(failed['PROJECT_DEPENDENCIES']['command'], ['npm', 'ci'])
        self.assertEqual(report['next'], list(failed.values()))

    def test_evidence_refuses_an_existing_output_before_measuring(self):
        project = self.populated()
        existing = self.base / 'check.json'
        existing.write_text('keep')
        code, report = self.vvv('evidence', '--project', str(project), '--output', str(existing))
        self.assertEqual((code, report['code']), (1, 'DESTINATION_EXISTS'))
        self.assertEqual(existing.read_text(), 'keep')

    def test_unknown_input_keys_warn_without_failing(self):
        (self.kit / 'schema').mkdir()
        (self.kit / 'schema' / 'doodle.json').write_text(json.dumps({
            'type': 'object', 'properties': {
                'copy': {'type': 'object', 'properties': {'title': {'type': 'string'}}},
                'music': {'type': 'object', 'properties': {'src': {'type': 'string'}}},
                'photos': {'type': 'object'}, 'fps': {'type': 'integer'}, 'format': {'type': 'string'}}}))
        project = self.populated()
        inputs = json.loads((project / 'inputs.json').read_text())
        inputs['props']['copy']['titel'] = 'typo'
        inputs['props']['music']['volumn'] = 1
        inputs['props']['colour'] = 'red'
        (project / 'inputs.json').write_text(json.dumps(inputs))
        report = validate_project(project)
        self.assertEqual(report['status'], 'passed')
        self.assertEqual(sorted((c['status'], c['location']) for c in report['checks']), [
            ('warning', 'inputs.json.props.colour'), ('warning', 'inputs.json.props.copy.titel'),
            ('warning', 'inputs.json.props.music.volumn')])
        self.assertEqual({c['code'] for c in report['checks']}, {'INPUT_UNKNOWN_KEY'})

    def test_galleries_prefer_photos_no_other_slot_uses(self):
        self.catalog['slots']['gallery'] = {'kind': 'array', 'count': 2, 'min': 1, 'max': 4, 'independent': True}
        ids = [{'id': f'p{i}'} for i in range(5)]
        photos, diagnostics = bind_photos(self.catalog, ids[:4])
        # Unused photos first, then reuse; the gallery keeps input order.
        self.assertEqual((photos['cover'], photos['pair'], photos['gallery']), ('p0', ['p1', 'p2'], ['p0', 'p3']))
        self.assertNotIn('PHOTOS_UNUSED', {d['code'] for d in diagnostics})
        photos, diagnostics = bind_photos(self.catalog, ids)
        self.assertEqual(photos['gallery'], ['p3', 'p4'])
        self.catalog['slots']['gallery']['count'] = 1
        photos, diagnostics = bind_photos(self.catalog, ids)
        unused = [d for d in diagnostics if d['code'] == 'PHOTOS_UNUSED']
        self.assertEqual(len(unused), 1)
        self.assertTrue(unused[0]['message'].startswith('1 photos'))

    def test_heic_without_a_decoder_is_named_in_the_diagnostics(self):
        from unittest.mock import patch
        self.photo('a.png')
        (self.photos / 'IMG_0001.HEIC').write_bytes(b'\x00\x00\x00\x18ftypheic')
        (self.photos / 'IMG_0002.heif').write_bytes(b'\x00\x00\x00\x18ftypheif')
        with patch.object(vvv_assets, 'HEIC_SUPPORT', False):
            items, diagnostics = inventory_images([self.photos])
            self.assertEqual(len(items), 1)
            self.assertEqual([d['code'] for d in diagnostics], ['HEIC_UNSUPPORTED', 'HEIC_UNSUPPORTED'])
            self.assertIn('pillow-heif', diagnostics[0]['message'])
            with self.assertRaisesRegex(ValueError, r'INSUFFICIENT_PHOTOS: .*2 HEIC/HEIF photos .*pillow-heif'):
                self.make_project()

    def test_projects_leave_kit_tests_behind_and_run_their_own_check(self):
        (self.kit / 'package.json').write_text(json.dumps({'private': True, 'scripts': {
            'typecheck': 'tsc --noEmit', 'test': 'node --test scripts/*.test.mjs',
            'check': 'npm run typecheck && npm test && node scripts/prepare-fonts.mjs --verify'}}))
        (self.kit / 'scripts').mkdir()
        (self.kit / 'scripts' / 'render.mjs').write_text('// render\n')
        (self.kit / 'scripts' / 'render.test.mjs').write_text('// test\n')
        (self.kit / 'src' / 'core').mkdir()
        (self.kit / 'src' / 'core' / 'timing.test.cjs').write_text('// test\n')
        project = self.populated()
        scripts = json.loads((project / 'package.json').read_text())['scripts']
        self.assertNotIn('test', scripts)
        self.assertEqual(scripts['check'], 'npm run typecheck && node scripts/prepare-fonts.mjs --verify')
        self.assertTrue((project / 'scripts' / 'render.mjs').is_file())
        self.assertFalse((project / 'scripts' / 'render.test.mjs').exists())
        self.assertFalse((project / 'src' / 'core' / 'timing.test.cjs').exists())

    def test_project_agent_notes_describe_a_project_directory(self):
        project = self.populated()
        agents = (project / 'AGENTS.md').read_text()
        self.assertIn('# project\n', agents)
        self.assertNotIn('package\n', agents.split('\n', 2)[1])
        self.assertIn('public/music/sources.json', agents)
        self.assertNotIn('licenses.json', agents)
        self.assertNotIn('vvv.json "downloads"', agents)
        self.assertIn('vvv:generated:end', agents)
        for name in ['AGENTS.md', 'PROJECT.md', 'inputs.json', '.gitignore']:
            self.assertNotIn(b'\r\n', (project / name).read_bytes(), name)

    def write_example(self, props_format=None):
        demo = self.kit / 'public' / 'photos' / 'demo'
        demo.mkdir()
        items = []
        for index, color in enumerate(['red', 'green', 'blue', 'white']):
            Image.new('RGB', (40, 30), color).save(demo / f'd{index}.jpg')
            items.append({'id': f'demo-{index}', 'file': f'photos/demo/d{index}.jpg', 'width': 40, 'height': 30,
                          'orientation': 'landscape', 'provenance': {'kind': 'fictional-demo'}})
        (self.kit / 'assets.json').write_text(json.dumps({'version': '0.1', 'items': items}))
        props = deepcopy(self.catalog['defaultProps'])
        props['photos'] = {'cover': 'demo-2', 'pair': ['demo-0', 'demo-1']}
        props['copy'] = {'title': 'Demo title'}
        if props_format:
            props['format'] = props_format
        (self.kit / 'examples').mkdir()
        (self.kit / 'examples' / 'doodle.json').write_text(json.dumps({'template': 'doodle', 'props': props}))
        self.catalog['package'] = {'name': '@test/doodle', 'fixture': 'examples/doodle.json'}
        self.write_catalog()

    def test_example_projects_use_the_shipped_demo_inputs(self):
        self.write_example()
        code, result = self.vvv('init', '--kit', str(self.kit), '--template', 'doodle', '--example',
                                '--output', str(self.base / 'example'))
        self.assertEqual((code, result['status'], result['example']), (0, 'created', 'examples/doodle.json'))
        project = self.base / 'example'
        inputs = json.loads((project / 'inputs.json').read_text())
        self.assertEqual(inputs['props']['photos'], {'cover': 'demo-2', 'pair': ['demo-0', 'demo-1']})
        self.assertEqual((inputs['props']['copy'], inputs['props']['format']), ({'title': 'Demo title'}, '16:9'))
        assets = json.loads((project / 'assets.json').read_text())['items']
        self.assertEqual([a['id'] for a in assets], ['demo-0', 'demo-1', 'demo-2'])
        self.assertEqual(sorted(p.name for p in (project / 'public' / 'photos').rglob('*.jpg')), ['d0.jpg', 'd1.jpg', 'd2.jpg'])
        self.assertFalse((project / 'public' / 'photos' / 'old-demo.jpg').exists())
        self.assertEqual(json.loads((project / 'creative' / 'intake.json').read_text())['selection'], 'example')
        self.assertTrue((project / 'creative' / 'contact-sheet.jpg').is_file())
        self.assertEqual(validate_project(project)['status'], 'passed')
        create_project(self.kit, 'doodle', [], self.base / 'vertical', frame_format='9:16', example=True)
        self.assertEqual(json.loads((self.base / 'vertical' / 'inputs.json').read_text())['props']['format'], '9:16')
        self.assertEqual(validate_project(self.base / 'vertical')['status'], 'passed')
        with self.assertRaisesRegex(ValueError, 'UNSUPPORTED_FORMAT'):
            create_project(self.kit, 'doodle', [], self.base / 'square', frame_format='1:1', example=True)
        del self.catalog['package']
        self.write_catalog()
        with self.assertRaisesRegex(ValueError, 'EXAMPLE_MISSING'):
            create_project(self.kit, 'doodle', [], self.base / 'none', example=True)
        self.assertFalse((self.base / 'none').exists())

    def test_describe_tells_an_agent_what_to_fill(self):
        self.catalog['formats']['9:16']['slots'] = ['cover']
        self.catalog['slots']['cover']['hint'] = 'The couple, facing the camera.'
        self.write_example(props_format='16:9')
        (self.kit / 'schema').mkdir()
        (self.kit / 'schema' / 'doodle.json').write_text(json.dumps({'type': 'object', 'properties': {
            'copy': {'type': 'object', 'properties': {'title': {'type': 'string', 'description': 'Opening title'}}},
            'accent': {'type': 'string', 'enum': ['warm', 'cool'], 'description': 'Colour accent'},
            'photos': {'type': 'object'}, 'fps': {'type': 'integer'}, 'format': {'type': 'string'},
            'music': {'type': 'object'}}}))
        code, record = self.vvv('describe', '--kit', str(self.kit), '--template', 'doodle', '--format', '9:16')
        self.assertEqual(code, 0)
        self.assertEqual(record['format'], '9:16')
        self.assertEqual(record['slots'], [{'name': 'cover', 'kind': 'single',
                                             'hint': 'The couple, facing the camera.'}])
        self.assertEqual(record['unusedSlots'], ['pair'])
        self.assertEqual([(f['name'], f['minPhotos'], f['sample']) for f in record['formats']],
                         [('16:9', 3, {'from': 1, 'to': 3}), ('9:16', 1, {'from': 1, 'to': 3})])
        self.assertEqual(record['copy'], {'title': 'Opening title'})
        self.assertIsNone(record['couple'])
        self.assertEqual(record['props'], {'accent': {'type': 'string', 'description': 'Colour accent', 'enum': ['warm', 'cool']}})
        self.assertEqual(record['music'], {'required': False, 'src': ''})
        self.assertEqual(record['fixture'], 'examples/doodle.json')
        self.assertTrue(all('--format 9:16' in n for n in record['next']))
        self.assertTrue(any('--example' in n for n in record['next']))

    def test_public_symlink_cannot_make_external_media_part_of_the_project(self):
        project = self.populated()
        external = self.base / 'external-public'
        (project / 'public').rename(external)
        (project / 'public').symlink_to(external, target_is_directory=True)
        result = validate_project(project)
        self.assertEqual(result['status'], 'failed')

    def test_intermediate_photo_symlink_is_rejected_even_inside_public(self):
        project = self.populated()
        photos = project / 'public' / 'photos'
        actual = project / 'public' / 'actual-photos'
        photos.rename(actual)
        photos.symlink_to(actual, target_is_directory=True)
        result = validate_project(project)
        self.assertEqual(result['status'], 'failed')

    def test_intermediate_music_symlink_is_rejected(self):
        project = self.populated()
        actual = project / 'public' / 'actual-music'
        actual.mkdir()
        (actual / 'track.wav').write_bytes(b'not decoded by structural validation')
        (project / 'public' / 'music').symlink_to(actual, target_is_directory=True)
        inputs = json.loads((project / 'inputs.json').read_text())
        inputs['props']['music']['src'] = 'music/track.wav'
        (project / 'inputs.json').write_text(json.dumps(inputs))
        self.assertEqual(validate_project(project)['status'], 'failed')

    def test_fingerprinted_symlinks_fail_validation_and_inspection(self):
        project = self.populated()
        directories = ['src', 'public', 'catalog', 'scripts', 'src/nested', 'public/assets',
                       'catalog/nested', 'scripts/nested']
        files = ['vvv.json', 'inputs.json', 'assets.json', 'package.json', 'package-lock.json',
                 'tsconfig.json', 'remotion.config.ts', 'src/index.tsx', 'public/decor.png']
        for relative in directories + files:
            with self.subTest(path=relative):
                target = project / relative
                if relative in directories:
                    target.mkdir(parents=True, exist_ok=True)
                elif not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text('review fixture')
                external = self.base / 'external-target'
                target.rename(external)
                target.symlink_to(external, target_is_directory=external.is_dir())
                try:
                    with self.assertRaisesRegex(ValueError, 'PROJECT_SYMLINK'):
                        project_fingerprint(project)
                    report = validate_project(project)
                    self.assertEqual(report['status'], 'failed')
                    self.assertIn('PROJECT_SYMLINK', {c['code'] for c in report['checks']})
                    result = self.run_cli('inspect', project)
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(result.stderr, '')
                    self.assertEqual(json.loads(result.stdout)['status'], 'failed')
                finally:
                    target.unlink()
                    external.rename(target)

    def test_fingerprint_orders_paths_by_utf8_bytes_like_the_renderer(self):
        import hashlib
        project = self.base / 'names'
        # U+FF5E sorts before U+1F600 by code point and UTF-8 bytes, after it by UTF-16 code units.
        names = ['src/\uff5e.ts', 'src/\U0001f600.ts', 'src/é.ts', 'src/z.ts', 'public/照片.txt']
        for name in names:
            (project / name).parent.mkdir(parents=True, exist_ok=True)
            (project / name).write_text(name)
        digest = hashlib.sha256()
        for name in sorted(names, key=lambda n: n.encode('utf-8')):
            digest.update(name.encode('utf-8') + b'\0' + hashlib.sha256(name.encode('utf-8')).digest())
        self.assertEqual(project_fingerprint(project), digest.hexdigest())
        import vvv_package
        entries = {n: hashlib.sha256(n.encode('utf-8')).hexdigest() for n in names}
        self.assertEqual(vvv_package.fingerprint_of(entries, []), digest.hexdigest())
        if not shutil.which('node'):
            self.skipTest('needs Node.js for the renderer side')
        support = (KIT / 'scripts' / 'render-support.mjs').as_uri()
        script = f"import {{ fingerprint }} from '{support}'; console.log(await fingerprint(process.argv[1]));"
        result = subprocess.run(['node', '--input-type=module', '-e', script, str(project)],
                                capture_output=True, text=True, timeout=60, check=True)
        self.assertEqual(result.stdout.strip(), digest.hexdigest())

    def test_tokens_accept_dv_pages_commas_whitespace_and_optional_at(self):
        project = self.populated()
        catalog = deepcopy(self.catalog)
        catalog['slots']['pair'] = {'kind': 'tokens', 'count': 2, 'min': 0}
        (project / 'catalog' / 'doodle.json').write_text(json.dumps(catalog))
        inputs = json.loads((project / 'inputs.json').read_text())
        first, second = inputs['props']['photos']['pair']
        for value in [f'@{first}|@{second}', f'{first},@{second}', f'@{first}，{second}',
                      f'  {first}\n@{second}\t', f'@{first}|{second}|@{first}', '', '| , ， ']:
            with self.subTest(value=value):
                inputs['props']['photos']['pair'] = value
                (project / 'inputs.json').write_text(json.dumps(inputs))
                self.assertEqual(validate_project(project)['status'], 'passed')

    def test_tokens_reject_malformed_ids_before_resolving_assets(self):
        project = self.populated()
        catalog = deepcopy(self.catalog)
        catalog['slots']['pair'] = {'kind': 'tokens', 'count': 2, 'min': 0}
        (project / 'catalog' / 'doodle.json').write_text(json.dumps(catalog))
        inputs = json.loads((project / 'inputs.json').read_text())
        for value in ['@_bad', '@-bad', '@', '@@photo', '../photo', 'photos/a.jpg', '@one#crop']:
            with self.subTest(value=value):
                inputs['props']['photos']['pair'] = value
                (project / 'inputs.json').write_text(json.dumps(inputs))
                self.assertIn('PHOTO_TOKEN', {c['code'] for c in validate_project(project)['checks']})

    def test_arrays_default_to_count_as_the_maximum(self):
        project = self.populated()
        inputs = json.loads((project / 'inputs.json').read_text())
        inputs['props']['photos']['pair'].append(inputs['props']['photos']['cover'])
        (project / 'inputs.json').write_text(json.dumps(inputs))
        self.assertIn('SLOT_COUNT', {c['code'] for c in validate_project(project)['checks']})

    def test_malformed_catalogs_return_structured_failures(self):
        project = self.populated()
        malformed = [[], None, {}, {**self.catalog, 'slots': []},
                     {**self.catalog, 'defaultProps': []}, {**self.catalog, 'sample': {'from': 2, 'to': 1}}]
        for slot in [None, [], {}, {'kind': [], 'count': 2}, {'kind': 'array', 'count': '2'},
                     {'kind': 'array', 'count': 2, 'min': -1},
                     {'kind': 'array', 'count': 2, 'min': 2, 'max': 1},
                     {'kind': 'array', 'count': 2, 'independent': 'yes'}]:
            malformed.append({**self.catalog, 'slots': {'pair': slot}})
        for catalog in malformed:
            with self.subTest(catalog=catalog):
                (project / 'catalog' / 'doodle.json').write_text(json.dumps(catalog))
                result = self.run_cli('validate', project)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stderr, '')
                report = json.loads(result.stdout)
                self.assertEqual(report['status'], 'failed')
                self.assertIn('CATALOG_INVALID', {c['code'] for c in report.get('checks', [])})

    def test_init_rejects_malformed_catalog_before_creating_output(self):
        self.photo('one.png')
        (self.kit / 'catalog' / 'doodle.json').write_text('[]')
        result = subprocess.run([sys.executable, str(SCRIPTS / 'vvv.py'), 'init',
                                 '--kit', str(self.kit), '--template', 'doodle',
                                 '--photos', str(self.photos), '--output', str(self.base / 'project'),
                                 '--allow-repeat'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, '')
        report = json.loads(result.stdout)
        self.assertEqual((report['status'], report['code']), ('failed', 'CATALOG_INVALID'))
        self.assertTrue(report['message'])
        self.assertFalse((self.base / 'project').exists())

    def test_inspect_exit_status_matches_failed_validation(self):
        project = self.populated()
        assets = json.loads((project / 'assets.json').read_text())
        (project / 'public' / assets['items'][0]['file']).unlink()
        result = self.run_cli('inspect', project)
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['validation']['status'], 'failed')

    def test_malformed_project_shapes_are_inspectable_without_tracebacks(self):
        project = self.populated()
        originals = {name: (project / name).read_text() for name in ['vvv.json', 'inputs.json', 'assets.json']}
        cases = [('vvv.json', []), ('inputs.json', []), ('assets.json', []),
                 ('inputs.json', {**json.loads(originals['inputs.json']), 'template': []}),
                 ('assets.json', {'version': '0.1', 'items': None})]
        for name, value in cases:
            with self.subTest(name=name, value=value):
                (project / name).write_text(json.dumps(value))
                try:
                    result = self.run_cli('inspect', project)
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(result.stderr, '')
                    self.assertEqual(json.loads(result.stdout)['status'], 'failed')
                finally:
                    (project / name).write_text(originals[name])

    def test_inspect_reports_nonobject_output_report_as_unreadable(self):
        project = self.populated()
        (project / 'out').mkdir()
        (project / 'out' / 'sample.report.json').write_text('[]')
        result = self.run_cli('inspect', project)
        self.assertEqual(result.stderr, '')
        report = json.loads(result.stdout)
        self.assertEqual(report['outputs'][0]['status'], 'unreadable')
        self.assertTrue(report['outputs'][0]['stale'])

    def write_output_report(self, project, **changes):
        report = {'status': 'rendered', 'mode': 'sample',
                  'fingerprint': project_fingerprint(project),
                  'output': 'out/sample.mp4', 'bytes': 5,
                  'compositionId': 'VVV-Doodle', 'sourceFrameRange': [30, 89],
                  'sourceTimeRange': {'from': 1, 'to': 3}, 'rangeEnd': 'inclusive',
                  'fps': 30, 'width': 960, 'height': 540, 'frames': 60,
                  'durationSeconds': 2, 'visualReview': 'not-reviewed'}
        report.update(changes)
        (project / 'out').mkdir(exist_ok=True)
        (project / 'out' / 'sample.report.json').write_text(json.dumps(report))

    def test_inspect_exposes_render_range_and_actual_file_without_claiming_decode(self):
        project = self.populated()
        self.write_output_report(project)
        (project / 'out' / 'sample.mp4').write_bytes(b'bytes')
        result = self.run_cli('inspect', project)
        self.assertEqual(result.returncode, 0)
        output = json.loads(result.stdout)['outputs'][0]
        self.assertEqual(output.get('output'), 'out/sample.mp4')
        self.assertEqual(output.get('sourceTimeRange'), {'from': 1, 'to': 3})
        self.assertEqual(output.get('sourceFrameRange'), [30, 89])
        self.assertEqual((output.get('fps'), output.get('width'), output.get('height')), (30, 960, 540))
        self.assertEqual(output.get('visualReview'), 'not-reviewed')
        self.assertEqual(output.get('artifact'), {'status': 'present', 'bytes': 5,
                                                'sizeChanged': False, 'decode': 'not-checked'})
        self.assertTrue(output.get('deliveryCandidate'))

    def test_inspect_distinguishes_missing_empty_and_nonfile_from_render_success(self):
        project = self.populated()
        self.write_output_report(project)
        artifact = project / 'out' / 'sample.mp4'
        for expected in ['missing', 'empty', 'non-file']:
            with self.subTest(expected=expected):
                if expected == 'empty':
                    artifact.touch()
                elif expected == 'non-file':
                    artifact.unlink()
                    artifact.mkdir()
                output = inspect_project(project)['outputs'][0]
                self.assertEqual(output['status'], 'rendered')
                self.assertFalse(output['stale'])
                self.assertEqual(output.get('artifact', {}).get('status'), expected)
                self.assertFalse(output.get('deliveryCandidate', True))

    def test_inspect_excludes_changed_size_stale_and_failed_output_candidates(self):
        project = self.populated()
        self.write_output_report(project)
        artifact = project / 'out' / 'sample.mp4'
        artifact.write_bytes(b'changed size')
        output = inspect_project(project)['outputs'][0]
        self.assertTrue(output.get('artifact', {}).get('sizeChanged'))
        self.assertEqual(output.get('artifact', {}).get('bytes'), 12)
        self.assertFalse(output.get('deliveryCandidate', True))
        artifact.write_bytes(b'bytes')
        self.write_output_report(project, fingerprint='older-revision')
        output = inspect_project(project)['outputs'][0]
        self.assertTrue(output['stale'])
        self.assertFalse(output.get('deliveryCandidate', True))
        self.write_output_report(project, status='source-changed-during-render')
        self.assertFalse(inspect_project(project)['outputs'][0].get('deliveryCandidate', True))

    def test_inspect_does_not_treat_legacy_report_as_verified_artifact(self):
        project = self.populated()
        self.write_output_report(project, output=None)
        output = inspect_project(project)['outputs'][0]
        self.assertEqual(output.get('artifact', {}).get('status'), 'unreported')
        self.assertFalse(output.get('deliveryCandidate', True))
        for size in [None, '5', True, -1]:
            with self.subTest(size=size):
                self.write_output_report(project, bytes=size)
                (project / 'out' / 'sample.mp4').write_bytes(b'bytes')
                output = inspect_project(project)['outputs'][0]
                self.assertIsNone(output.get('artifact', {}).get('sizeChanged'))
                self.assertFalse(output.get('deliveryCandidate', True))

    def test_inspect_rejects_escaping_and_symlink_output_paths(self):
        project = self.populated()
        external = self.base / 'external.mp4'
        external.write_bytes(b'private external bytes')
        self.write_output_report(project)
        (project / 'out' / 'linked.mp4').symlink_to(external)
        (project / 'out' / 'linked-folder').symlink_to(self.base, target_is_directory=True)
        for value in ['../external.mp4', str(external), 'out/linked.mp4',
                      'out/linked-folder/external.mp4', 'out\\sample.mp4', 'out/\x00.mp4']:
            with self.subTest(path=value):
                self.write_output_report(project, output=value)
                output = inspect_project(project)['outputs'][0]
                self.assertEqual(output.get('artifact', {}).get('status'), 'unsafe')
                self.assertIsNone(output.get('artifact', {}).get('bytes'))
                self.assertFalse(output.get('deliveryCandidate', True))

    def test_inspect_does_not_follow_linked_render_reports(self):
        project = self.populated()
        self.write_output_report(project)
        report = project / 'out' / 'sample.report.json'
        external = self.base / 'external-report.json'
        report.rename(external)
        report.symlink_to(external)
        output = inspect_project(project)['outputs'][0]
        self.assertEqual(output['status'], 'unreadable')
        self.assertTrue(output['stale'])
        self.assertFalse(output.get('deliveryCandidate', True))

    def test_inspect_reports_unreadable_artifact_without_claiming_it_is_missing(self):
        project = self.populated()
        self.write_output_report(project)
        artifact = project / 'out' / 'sample.mp4'
        artifact.write_bytes(b'bytes')
        artifact.chmod(0)
        try:
            try:
                artifact.read_bytes()
            except PermissionError:
                pass
            else:
                self.skipTest('This user can read mode-000 files.')
            output = inspect_project(project)['outputs'][0]
            self.assertEqual(output['status'], 'rendered')
            self.assertEqual(output.get('artifact', {}).get('status'), 'unreadable')
            self.assertFalse(output.get('deliveryCandidate', True))
        finally:
            artifact.chmod(0o600)

    def test_music_src_requires_a_string_even_when_falsy(self):
        project = self.populated()
        inputs = json.loads((project / 'inputs.json').read_text())
        for value in [None, [], {}, 0, False]:
            with self.subTest(value=value):
                inputs['props']['music']['src'] = value
                (project / 'inputs.json').write_text(json.dumps(inputs))
                self.assertEqual(validate_project(project)['status'], 'failed')

    def test_templates_are_discovered_from_kit_catalogs(self):
        other = {**deepcopy(self.catalog), 'id': 'beat-reel', 'title': 'Beat reel', 'music': {'required': True}}
        (self.kit / 'catalog' / 'beat-reel.json').write_text(json.dumps(other))
        (self.kit / 'catalog' / 'Not_A_Template.json').write_text('{}')
        listed = {t['id']: t for t in list_templates(self.kit)}
        self.assertEqual(set(listed), {'doodle', 'beat-reel'})
        self.assertEqual(listed['beat-reel']['formats'], [
            {'name': '16:9', 'width': 1920, 'height': 1080, 'minPhotos': 3, 'targetPhotos': 3},
            {'name': '9:16', 'width': 1080, 'height': 1920, 'minPhotos': 3, 'targetPhotos': 3}])
        self.assertEqual(listed['beat-reel']['defaultFormat'], '16:9')
        self.assertEqual(listed['beat-reel']['description'], '')
        self.assertTrue(listed['beat-reel']['musicRequired'])
        self.photo('a.png')
        with self.assertRaisesRegex(ValueError, 'UNKNOWN_TEMPLATE'):
            create_project(self.kit, 'missing', [self.photos], self.base / 'missing')
        with self.assertRaisesRegex(ValueError, 'UNKNOWN_TEMPLATE'):
            create_project(self.kit, '../doodle', [self.photos], self.base / 'escape')

    def test_format_defaults_and_explicit_choice_are_recorded(self):
        self.photo('a.png', 'red')
        self.photo('b.png', 'green')
        self.photo('c.png', 'blue')
        self.make_project()
        inputs = json.loads((self.base / 'project' / 'inputs.json').read_text())
        self.assertEqual(inputs['props']['format'], '16:9')
        result = create_project(self.kit, 'doodle', [self.photos], self.base / 'vertical', frame_format='9:16')
        self.assertEqual(result['format'], '9:16')
        vertical = self.base / 'vertical'
        self.assertEqual(json.loads((vertical / 'inputs.json').read_text())['props']['format'], '9:16')
        self.assertEqual(validate_project(vertical)['status'], 'passed')
        self.assertIn('public/music/mixkit-*.mp3', (vertical / '.gitignore').read_text())

    def test_unsupported_format_is_rejected_before_output_and_in_validation(self):
        self.photo('a.png', 'red')
        self.photo('b.png', 'green')
        self.photo('c.png', 'blue')
        with self.assertRaisesRegex(ValueError, 'UNSUPPORTED_FORMAT'):
            create_project(self.kit, 'doodle', [self.photos], self.base / 'square', frame_format='1:1')
        self.assertFalse((self.base / 'square').exists())
        project = self.populated_existing()
        inputs = json.loads((project / 'inputs.json').read_text())
        inputs['props']['format'] = '1:1'
        (project / 'inputs.json').write_text(json.dumps(inputs))
        failed = [c['code'] for c in validate_project(project)['checks'] if c['status'] == 'failed']
        self.assertEqual(failed, ['FORMAT'])

    def test_a_format_may_declare_its_own_sample_window(self):
        self.catalog['formats']['9:16']['sample'] = {'from': 6, 'to': 22}
        self.write_catalog()
        project = self.populated()
        self.assertEqual(validate_project(project)['status'], 'passed')

    def test_templates_without_photo_slots_initialize_without_photos(self):
        title_card = {**deepcopy(self.catalog), 'id': 'title-card', 'slots': {}, 'defaultProps': {'copy': {}, 'fps': 30, 'music': {'src': ''}, 'photos': {}}}
        (self.kit / 'catalog' / 'title-card.json').write_text(json.dumps(title_card))
        result = create_project(self.kit, 'title-card', [], self.base / 'title-card')
        self.assertEqual(result['assetCount'], 0)
        self.assertEqual(validate_project(self.base / 'title-card')['status'], 'passed')
        self.assertFalse((self.base / 'title-card' / 'creative' / 'contact-sheet.jpg').exists())
        with self.assertRaisesRegex(ValueError, 'PHOTOS_REQUIRED'):
            create_project(self.kit, 'doodle', [], self.base / 'no-photos')

    def populated_existing(self):
        self.make_project()
        return self.base / 'project'

    def test_catalog_formats_are_validated(self):
        project = self.populated()
        bad = [
            {**self.catalog, 'formats': {}},
            {**self.catalog, 'formats': {'wide': {'width': 1920, 'height': 1080}}},
            {**self.catalog, 'formats': {'16:9': {'width': 1921, 'height': 1080}}},
            {**self.catalog, 'formats': {'16:9': {'width': 1920}}},
            {**self.catalog, 'defaultFormat': '4:5'},
            {**self.catalog, 'music': {'required': 'yes'}},
            {**self.catalog, 'check': {'maxStillSeconds': 0}},
            {**self.catalog, 'formats': {'16:9': {'width': 1920, 'height': 1080, 'sample': {'from': 5, 'to': 2}}}},
            {**self.catalog, 'formats': {'16:9': {'width': 1920, 'height': 1080, 'sample': {'from': 0}}}},
        ]
        for catalog in bad:
            with self.subTest(catalog=catalog):
                (project / 'catalog' / 'doodle.json').write_text(json.dumps(catalog))
                result = validate_project(project)
                self.assertEqual(result['status'], 'failed')
                self.assertIn('CATALOG_INVALID', result['checks'][-1]['code'])

    def test_music_required_templates_fail_validation_without_music(self):
        self.catalog['music'] = {'required': True}
        self.write_catalog()
        self.photo('a.png', 'red')
        self.photo('b.png', 'green')
        self.photo('c.png', 'blue')
        with self.assertRaisesRegex(ValueError, 'MUSIC_REQUIRED'):
            self.make_project()
        self.assertFalse((self.base / 'project').exists())

    def test_download_only_music_is_pending_until_fetched(self):
        music = self.kit / 'public' / 'music'
        music.mkdir(parents=True)
        (music / 'sources.json').write_text(json.dumps({'version': '0.1', 'tracks': [
            {'file': 'mixkit-skyline.mp3', 'distribution': 'download'},
            {'file': 'bundled.ogg', 'distribution': 'bundled'}]}))
        self.catalog['music'] = {'required': True}
        self.catalog['defaultProps']['music']['src'] = 'music/mixkit-skyline.mp3'
        self.write_catalog()
        self.photo('a.png', 'red')
        self.photo('b.png', 'green')
        self.photo('c.png', 'blue')
        result = self.make_project()
        self.assertIn('npm run music', result['next'])
        project = self.base / 'project'
        validation = validate_project(project)
        self.assertEqual(validation['status'], 'pending')
        self.assertEqual([c['code'] for c in validation['checks'] if c['status'] != 'passed'], ['MUSIC_DOWNLOAD_PENDING'])
        (project / 'public' / 'music' / 'mixkit-skyline.mp3').write_bytes(b'audio')
        self.assertEqual(validate_project(project)['status'], 'passed')
        # Files a template plays on its own (here a sound effect) are pending until fetched as well.
        sources = json.loads((project / 'public' / 'music' / 'sources.json').read_text())
        sources['tracks'].append({'file': 'mixkit-pop.wav', 'dir': 'sfx', 'distribution': 'download', 'templates': ['doodle']})
        (project / 'public' / 'music' / 'sources.json').write_text(json.dumps(sources))
        pending = validate_project(project)
        self.assertEqual(pending['status'], 'pending')
        self.assertEqual([c['location'] for c in pending['checks'] if c['status'] == 'pending'], ['public/sfx/mixkit-pop.wav'])
        (project / 'public' / 'sfx').mkdir()
        (project / 'public' / 'sfx' / 'mixkit-pop.wav').write_bytes(b'fx')
        self.assertEqual(validate_project(project)['status'], 'passed')
        # A bundled or unlisted track that is missing is an error, not a pending download.
        inputs = json.loads((project / 'inputs.json').read_text())
        inputs['props']['music']['src'] = 'music/bundled.ogg'
        (project / 'inputs.json').write_text(json.dumps(inputs))
        self.assertEqual([c['code'] for c in validate_project(project)['checks'] if c['status'] == 'failed'], ['MUSIC_FILE'])

    def test_format_slots_relax_unused_slots_only_in_that_format(self):
        self.catalog['formats']['9:16']['slots'] = ['cover']
        self.write_catalog()
        self.photo('a.png')
        with self.assertRaisesRegex(ValueError, r'INSUFFICIENT_PHOTOS: doodle \(16:9\) needs at least 3'):
            self.make_project()
        create_project(self.kit, 'doodle', [self.photos], self.base / 'vertical', frame_format='9:16')
        vertical = self.base / 'vertical'
        inputs = json.loads((vertical / 'inputs.json').read_text())
        self.assertEqual(inputs['props']['photos']['pair'], [])
        self.assertEqual(validate_project(vertical)['status'], 'passed')
        inputs['props']['format'] = '16:9'
        (vertical / 'inputs.json').write_text(json.dumps(inputs))
        failed = [(c['code'], c['location']) for c in validate_project(vertical)['checks'] if c['status'] == 'failed']
        self.assertEqual(failed, [('SLOT_COUNT', 'inputs.json.props.photos.pair')])

    def test_format_slots_must_name_declared_slots(self):
        project = self.populated()
        for used in [['cover', 'missing'], ['cover', 'cover'], 'cover']:
            with self.subTest(slots=used):
                catalog = deepcopy(self.catalog)
                catalog['formats']['9:16']['slots'] = used
                (project / 'catalog' / 'doodle.json').write_text(json.dumps(catalog))
                self.assertIn('CATALOG_INVALID', {c['code'] for c in validate_project(project)['checks']})

    def test_props_schema_travels_with_the_project_and_is_enforced(self):
        (self.kit / 'schema').mkdir()
        (self.kit / 'schema' / 'doodle.json').write_text(json.dumps({
            'type': 'object', 'required': ['copy', 'photos', 'music'],
            'properties': {
                'copy': {'type': 'object', 'required': ['title'],
                         'properties': {'title': {'type': 'string', 'description': 'Opening title'}}},
                'music': {'type': 'object', 'properties': {'src': {'type': 'string'},
                                                           'volume': {'type': 'number', 'minimum': 0, 'maximum': 1}}},
                'photos': {'type': 'object', 'required': ['cover']}}}))
        project = self.populated()
        self.assertTrue((project / 'schema' / 'props.schema.json').is_file())
        report = validate_project(project)
        self.assertEqual(report['status'], 'passed')
        self.assertIn('input-schema', report['scope'])
        inputs = json.loads((project / 'inputs.json').read_text())

        def failures(change):
            changed = deepcopy(inputs)
            change(changed['props'])
            (project / 'inputs.json').write_text(json.dumps(changed))
            return [c for c in validate_project(project)['checks'] if c['status'] == 'failed']

        [kicker] = failures(lambda p: p['copy'].update(title=42))
        self.assertEqual((kicker['code'], kicker['location']), ('INPUT_SCHEMA', 'inputs.json.props.copy.title'))
        self.assertIn('Opening title', kicker['message'])
        self.assertEqual([c['location'] for c in failures(lambda p: p.update(copy=None))], ['inputs.json.props.copy'])
        self.assertEqual([c['location'] for c in failures(lambda p: p['music'].update(volume='loud'))],
                         ['inputs.json.props.music.volume'])
        # A missing top-level prop takes the template default at render time.
        self.assertEqual(failures(lambda p: p.pop('copy')), [])
        # A field with its own check is reported once.
        self.assertEqual([c['code'] for c in failures(lambda p: p['music'].update(src=None))], ['MUSIC_TYPE'])
        (project / 'schema' / 'props.schema.json').unlink()
        self.assertIn('input-schema', validate_project(project)['notChecked'])


KIT = Path(__file__).resolve().parents[1] / 'kits' / 'remotion'


class KitReuseTests(unittest.TestCase):
    """The shipped catalogs: every legal photo count initializes, and validate agrees with the renderer."""

    @staticmethod
    def assets(count):
        return [{'id': f'p{i:03d}'} for i in range(count)]

    def test_templates_report_photo_needs_per_format(self):
        listed = {t['id']: t for t in list_templates(KIT)}
        self.assertEqual({f['name']: (f['minPhotos'], f['targetPhotos']) for f in listed['album']['formats']},
                         {'16:9': (40, 40), '9:16': (2, 37)})
        self.assertEqual({f['name']: (f['minPhotos'], f['targetPhotos']) for f in listed['starter']['formats']},
                         {'16:9': (8, 14), '9:16': (8, 14)})
        self.assertTrue(all(t['description'] for t in listed.values()))

    def test_describe_is_compact_for_the_shipped_templates(self):
        for template in ['album', 'starter', 'comedy', 'doodle', 'dv-story']:
            with self.subTest(template=template):
                record = describe_template(KIT, template)
                size = len(json.dumps(record, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
                # Album has 27 slots, each with a placement hint, and Comedy 30 copy fields; with the emotional arc,
                # about 2k tokens is still far less than their source.
                self.assertLess(size, 6656 if template == 'album' else 8704)
                self.assertTrue(record['copy'])
                self.assertEqual(record['fixture'], load_catalog(KIT, template)['package']['fixture'])
        album = describe_template(KIT, 'album', '9:16')
        self.assertEqual([s['name'] for s in album['slots']], ['opening', 'ending', 'gallery'])
        gallery = {k: v for k, v in album['slots'][2].items() if k != 'hint'}
        self.assertEqual(gallery, {'name': 'gallery', 'kind': 'array', 'min': 1, 'count': 37, 'independent': True})
        self.assertIn('bride', album['unusedSlots'])
        self.assertEqual(album['music']['src'], 'music/mixkit-skyline.mp3')

    def test_the_doodle_example_initializes_a_valid_project(self):
        output = Path(tempfile.mkdtemp()) / 'doodle'
        self.addCleanup(shutil.rmtree, output.parent)
        result = create_project(KIT, 'doodle', [], output, example=True)
        self.assertEqual(result['status'], 'created')
        self.assertNotEqual(validate_project(output)['status'], 'failed')
        fixture = json.loads((KIT / load_catalog(KIT, 'doodle')['package']['fixture']).read_text())['props']
        self.assertEqual(json.loads((output / 'inputs.json').read_text())['props']['photos'], fixture['photos'])
        self.assertFalse(list(output.rglob('*.test.mjs')))
        self.assertNotIn('test', json.loads((output / 'package.json').read_text())['scripts'])

    def test_starter_fills_every_slot_from_its_minimum_to_its_target(self):
        catalog = load_catalog(KIT, 'starter')
        for count, gallery in [(8, 6), (13, 11), (14, 12), (30, 12)]:
            with self.subTest(photos=count):
                photos, diagnostics = bind_photos(catalog, self.assets(count))
                used = [photos['opening'], *photos['gallery'], photos['ending']]
                self.assertEqual(len(photos['gallery']), gallery)
                self.assertEqual(used, [f'p{i:03d}' for i in range(len(used))])  # input order, nothing repeated
                self.assertEqual('PHOTOS_UNUSED' in {d['code'] for d in diagnostics}, count > 14)
        with self.assertRaisesRegex(ValueError, r'INSUFFICIENT_PHOTOS: starter \(16:9\) needs at least 8 .*got 7'):
            bind_photos(catalog, self.assets(7))
        photos, diagnostics = bind_photos(catalog, self.assets(7), allow_repeat=True)
        self.assertEqual(len(photos['gallery']), 6)
        self.assertTrue(photos['ending'])
        self.assertIn('PHOTO_REUSED', {d['code'] for d in diagnostics})

    def test_album_vertical_needs_only_the_slots_the_short_shows(self):
        catalog = load_catalog(KIT, 'album')
        photos, diagnostics = bind_photos(catalog, self.assets(3), frame_format='9:16')
        self.assertEqual((photos['opening'], photos['ending']), ('p000', 'p001'))
        self.assertEqual(photos['gallery'], ['p000', 'p001', 'p002'])
        self.assertEqual((photos['bride'], photos['poem']), ('', []))
        self.assertEqual(diagnostics, [])
        with self.assertRaisesRegex(ValueError, r'album \(16:9\) needs at least 40'):
            bind_photos(catalog, self.assets(12), frame_format='16:9')
        photos, _ = bind_photos(catalog, self.assets(40))
        story = [v for name, v in photos.items() if name != 'gallery' for v in (v if isinstance(v, list) else [v])]
        self.assertEqual(len(story), 40)
        self.assertEqual(len(set(story)), 40)

    def test_dv_story_optional_chapters_fill_in_order(self):
        catalog = load_catalog(KIT, 'dv-story')
        photos, _ = bind_photos(catalog, self.assets(3))
        self.assertEqual((photos['birth1'], photos['birth2'], photos['childhood']), ('@p000', '@p001', '@p002'))
        self.assertEqual(photos['fate'], '')

    @unittest.skipUnless(shutil.which('node') and (KIT / 'node_modules' / 'zod').is_dir(),
                         'needs Node.js and the kit dependencies (npm --prefix kits/remotion ci)')
    def test_validate_and_the_renderer_accept_and_reject_the_same_inputs(self):
        mutations = {
            'valid': lambda p: None,
            'couple null': lambda p: p.update(couple=None),
            'copy null': lambda p: p.update(copy=None),
            'copy line number': lambda p: p['copy'].update({next(iter(p['copy'])): 42}),
            'copy line missing': lambda p: p['copy'].pop(next(iter(p['copy']))),
            'volume text': lambda p: p['music'].update(volume='loud'),
            'volume above 1': lambda p: p['music'].update(volume=2),
            'negative trim': lambda p: p['music'].update(trimBeforeSec=-1),
            'music src null': lambda p: p['music'].update(src=None),
            'fractional fps': lambda p: p.update(fps=23.5),
            'boolean fps': lambda p: p.update(fps=True),
            'bad format': lambda p: p.update(format='wide'),
            'unknown prop': lambda p: p.update(somethingElse=1),
            'music omitted': lambda p: p.pop('music'),
            'numbers as text': lambda p: p.update({k: 'x' for k, v in p.items()
                                                   if isinstance(v, (int, float)) and not isinstance(v, bool)}),
        }
        cases = []
        for template in ['starter', 'album', 'comedy', 'doodle', 'dv-story']:
            catalog = load_catalog(KIT, template)
            fixture = json.loads((KIT / catalog['package']['fixture']).read_text())['props']
            for name, mutate in mutations.items():
                props = deepcopy(fixture)
                mutate(props)
                checks = []
                input_schema_checks(KIT, template, props, checks)
                cases.append({'case': f'{template}: {name}', 'template': template, 'props': props,
                              'python': all(c['status'] != 'failed' for c in checks)})
                # zod drops keys its schema does not declare; validate warns instead of failing.
                unknown = [c['location'] for c in checks if c['code'] == 'INPUT_UNKNOWN_KEY']
                if name in ('valid', 'unknown prop'):
                    self.assertEqual(unknown, ['inputs.json.props.somethingElse'] if name == 'unknown prop' else [])
        script = ("require('./scripts/export-schemas.cjs');"
                  "const { TEMPLATES } = require('./src/templates/registry.ts');"
                  "const cases = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));"
                  "console.log(JSON.stringify(cases.map((c) => { const d = TEMPLATES[c.template].definition;"
                  " return d.schema.safeParse({ ...d.defaultProps, ...c.props }).success; })));")
        result = subprocess.run(['node', '-e', script], cwd=KIT, input=json.dumps(cases), capture_output=True,
                                text=True, timeout=300, check=True)
        runtime = json.loads(result.stdout)
        disagreements = [(c['case'], c['python'], r) for c, r in zip(cases, runtime) if c['python'] != r]
        self.assertEqual(disagreements, [])
        self.assertGreater(runtime.count(False), len(cases) // 2)


if __name__ == '__main__':
    unittest.main()

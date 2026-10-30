"""Reference-layout measurement and Chrome reuse, without FFmpeg or a network."""

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills' / 'vvv' / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import vvv_doctor  # noqa: E402
import vvv_ref  # noqa: E402


class LayoutTests(unittest.TestCase):
    def test_regions_finds_photo_boxes_and_text_on_paper(self):
        frame = Image.new('RGB', (1920, 1080), (253, 252, 250))
        draw = ImageDraw.Draw(frame)
        draw.rectangle([0, 0, 1043, 1079], fill=(90, 110, 130))        # photo on the left edge
        draw.rectangle([1400, 300, 1799, 799], fill=(160, 40, 60))      # a second photo
        for x in range(1100, 1360, 30):                                 # a line of text
            draw.rectangle([x, 950, x + 14, 970], fill=(40, 40, 40))
        result = vvv_ref.regions(frame, 40000)
        self.assertEqual(result['paper'], '#fcfcfc')
        self.assertEqual([(b['x'], b['y'], b['w'], b['h']) for b in result['photos']], [(0, 0, 1044, 1080), (1400, 300, 400, 500)])
        self.assertGreater(result['marks'], 5)
        self.assertEqual(result['markExtent']['y'], 948)

    def test_sheets_tile_labelled_frames(self):
        frames = [vvv_ref.labelled(Image.new('RGB', (1920, 1080), (n * 30, 0, 0)), f'{n:.2f}', 320) for n in range(7)]
        sheet = vvv_ref.tile(frames, 3)
        self.assertEqual(sheet.size, (3 * 320 + 2 * 6, 3 * 180 + 2 * 6))


class ChromeReuseTests(unittest.TestCase):
    def test_a_project_gets_the_cached_shell_and_a_new_download_is_cached(self):
        base = Path(tempfile.mkdtemp())
        cache = base / 'cache' / 'chrome-headless-shell'
        with patch.object(vvv_doctor, 'CACHE', cache):
            project = base / 'project'
            self.assertIsNone(vvv_doctor.provide_chrome(project, None))
            downloaded = project / vvv_doctor.SHELL / 'mac-arm64'
            downloaded.mkdir(parents=True)
            (downloaded / 'chrome-headless-shell').write_text('binary')
            vvv_doctor.cache_chrome(project)
            self.assertTrue((cache / 'mac-arm64' / 'chrome-headless-shell').is_file())
            second = base / 'second'
            self.assertEqual(vvv_doctor.provide_chrome(second, None), str(cache))
            self.assertTrue((second / vvv_doctor.SHELL / 'mac-arm64' / 'chrome-headless-shell').is_file())
            self.assertEqual(vvv_doctor.provide_chrome(second, None), 'project')


if __name__ == '__main__':
    unittest.main()

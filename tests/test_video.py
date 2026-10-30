"""Offline tests for the TikHub route: the API and the video CDN are a local fixture server."""

from contextlib import contextmanager, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills' / 'vvv' / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import vvv_video as video  # noqa: E402

MP4 = b'\x00\x00\x00\x18ftypmp42' + bytes(4096)
SECRET = 'fixture-only-tikhub-token'


class VideoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name) / 'refs'
        env = patch.dict(os.environ, {'no_proxy': '127.0.0.1,localhost', 'NO_PROXY': '127.0.0.1,localhost'})
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop('TIKHUB_API_KEY', None)
        token_file = patch.object(video, 'TOKEN_FILE', Path(self.temp.name) / 'no-token')
        token_file.start()
        self.addCleanup(token_file.stop)

    @contextmanager
    def server(self, status=200, reply=None):
        calls = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                calls.append({'path': self.path, 'auth': self.headers.get('Authorization'), 'referer': self.headers.get('Referer')})
                if self.path.startswith('/cdn/'):
                    self.send_response(200)
                    self.send_header('Content-Type', 'video/mp4')
                    self.end_headers()
                    self.wfile.write(MP4)
                    return
                base = f'http://127.0.0.1:{self.server.server_port}/cdn'
                body = reply(base) if reply else {
                    'code': 200, 'data': {'type': 'video', 'platform': 'douyin', 'video_id': '7400000000000000001', 'desc': '婚礼 MV 参考',
                                          'author': {'avatar_url': f'{base}/avatar.jpg'},
                                          'cover_data': {'cover': {'url_list': [f'{base}/cover.jpg']}},
                                          'video_data': {'wm_video_url_HQ': f'{base}/wm.mp4', 'nwm_video_url_HQ': f'{base}/nwm.mp4'}}}
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            with patch.object(video, 'API', f'http://127.0.0.1:{httpd.server_port}'):
                yield calls
        finally:
            httpd.shutdown()
            httpd.server_close()

    def call(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = video.main(list(argv))
        return code, json.loads(out.getvalue()), out.getvalue()

    def test_douyin_share_text_downloads_the_unwatermarked_video_with_a_record(self):
        with patch.dict(os.environ, {'TIKHUB_API_KEY': SECRET}), self.server() as calls:
            code, result, text = self.call('fetch', '--url', '复制打开抖音 https://v.douyin.com/AbCdEf/ 看看', '--output', str(self.out))
        self.assertEqual(code, 0, text)
        self.assertEqual(Path(result['file']).read_bytes(), MP4)
        self.assertEqual(Path(result['file']).name, 'douyin-7400000000000000001.mp4')
        record = json.loads(Path(result['record']).read_text())
        self.assertEqual((record['platform'], record['title']), ('douyin', '婚礼 MV 参考'))
        self.assertIn('Reference for study only', record['use'])
        api, cdn = calls[0], calls[1]
        self.assertTrue(api['path'].startswith('/api/v1/hybrid/video_data?url='))
        self.assertEqual(api['auth'], f'Bearer {SECRET}')
        self.assertEqual((cdn['path'], cdn['auth'], cdn['referer']), ('/cdn/nwm.mp4', None, 'https://www.douyin.com/'))
        self.assertNotIn(SECRET, text)

    def test_platforms_route_to_their_endpoints(self):
        for n, (link, endpoint) in enumerate((('https://xhslink.com/a/xyz', '/api/v1/xiaohongshu/app_v2/get_video_note_detail?share_text='),
                               ('复制打开【小红书】 https://xhslink.cn/o/9O5fYaj2Off 看全文', '/api/v1/xiaohongshu/app_v2/get_video_note_detail?share_text='),
                               ('https://v.kuaishou.com/abc', '/api/v1/kuaishou/app/fetch_one_video_by_url?share_text='),
                               ('https://www.tiktok.com/@a/video/1', '/api/v1/hybrid/video_data?url='))):
            nested = lambda base: {'data': {'note_list': [{'video': {'media': {'stream': {'h264': [{'master_url': f'{base}/x.mp4'}]}}}}]}}
            with patch.dict(os.environ, {'TIKHUB_API_KEY': SECRET}), self.server(reply=nested) as calls:
                code, result, text = self.call('fetch', '--url', link, '--output', str(self.out), '--name', f'case-{n}')
            self.assertEqual(code, 0, text)
            self.assertTrue(calls[0]['path'].startswith(endpoint), calls[0]['path'])

    def test_the_requested_post_and_its_sharpest_stream_win(self):
        def feed(base):
            stream = lambda name, w, h: {'width': w, 'height': h, 'master_url': f'{base}/{name}.mp4'}
            note = lambda tag: {'video_info_v2': {'media': {'stream': {'h265': [stream(f'{tag}-720', 1280, 720), stream(f'{tag}-1080', 1920, 1080)],
                                                                         'h264': [stream(f'{tag}-h264', 1280, 720)]}}}}
            return {'data': {'success': True, 'data': [note('asked'), note('recommended')]}}
        with patch.dict(os.environ, {'TIKHUB_API_KEY': SECRET}), self.server(reply=feed) as calls:
            code, result, text = self.call('fetch', '--url', 'https://xhslink.cn/o/abc', '--output', str(self.out))
        self.assertEqual(code, 0, text)
        self.assertEqual(calls[1]['path'], '/cdn/asked-1080.mp4')

    def test_missing_token_asks_the_user_and_calls_nothing(self):
        with self.server() as calls:
            code, result, _ = self.call('fetch', '--url', 'https://v.douyin.com/x/', '--output', str(self.out))
        self.assertEqual((code, result['code'], result['next']['action'], calls), (1, 'TOKEN_MISSING', 'ask_user', []))

    def test_bilibili_and_unknown_links_are_refused_before_any_request(self):
        with patch.dict(os.environ, {'TIKHUB_API_KEY': SECRET}), self.server() as calls:
            code, result, _ = self.call('fetch', '--url', 'https://b23.tv/abc', '--output', str(self.out))
            code2, result2, _ = self.call('fetch', '--url', 'https://example.com/v.mp4', '--output', str(self.out))
        self.assertEqual((result['code'], result2['code'], calls), ('UNSUPPORTED_PLATFORM', 'UNSUPPORTED_PLATFORM', []))

    def test_low_balance_becomes_a_question(self):
        with patch.dict(os.environ, {'TIKHUB_API_KEY': SECRET}), self.server(status=402):
            code, result, _ = self.call('fetch', '--url', 'https://v.douyin.com/x/', '--output', str(self.out))
        self.assertEqual((code, result['code'], result['next']['action']), (1, 'BALANCE', 'ask_user'))

    def test_a_photo_note_without_video_writes_nothing(self):
        photo = lambda base: {'data': {'images_list': [{'url': f'{base}/img.jpg'}], 'cover': {'url': f'{base}/c.jpg'}}}
        with patch.dict(os.environ, {'TIKHUB_API_KEY': SECRET}), self.server(reply=photo):
            code, result, _ = self.call('fetch', '--url', 'https://xhslink.com/a/x', '--output', str(self.out))
        self.assertEqual((code, result['code']), (1, 'NO_VIDEO'))
        self.assertFalse(self.out.exists() and any(self.out.iterdir()))


if __name__ == '__main__':
    unittest.main()

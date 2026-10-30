#!/usr/bin/env python3
"""A reference video from a share link (抖音, TikTok, 小红书, 快手), fetched through the user's TikHub account.

  doctor                                  is a TikHub token configured? (never printed)
  fetch --url LINK_OR_SHARE_TEXT --output DIR [--name NAME]
                                          resolve the post, download its video without watermark into DIR
                                          and write DIR/NAME.source.json beside it

The token comes from TIKHUB_API_KEY, else from ~/.config/vvv/tikhub-token, a file the user writes
themselves. TikHub bills each request to the user's balance. A fetched video is a reference to study:
it is never shipped, packed or used as footage without the rights holder's permission.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

from vvv import ask_user, emit, fix, run

API = os.environ.get('VVV_TIKHUB_API', 'https://api.tikhub.io').rstrip('/')
TOKEN_FILE = Path('~/.config/vvv/tikhub-token').expanduser()
MAX_BYTES = 1024 * 1024 * 1024
TIMEOUT = 90
UA = ('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 '
      '(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1')
# Host fragments → (platform, endpoint, query parameter). 抖音 and TikTok share one hybrid parser.
PLATFORMS = [
    (('douyin.com', 'iesdouyin.com'), 'douyin', '/api/v1/hybrid/video_data', 'url'),
    (('tiktok.com',), 'tiktok', '/api/v1/hybrid/video_data', 'url'),
    (('xhslink.com', 'xhslink.cn', 'xiaohongshu.com'), 'xiaohongshu', '/api/v1/xiaohongshu/app_v2/get_video_note_detail', 'share_text'),
    (('kuaishou.com', 'chenzhongtech.com', 'gifshow.com'), 'kuaishou', '/api/v1/kuaishou/app/fetch_one_video_by_url', 'share_text'),
]
REFERERS = {'douyin': 'https://www.douyin.com/', 'tiktok': 'https://www.tiktok.com/',
            'xiaohongshu': 'https://www.xiaohongshu.com/', 'kuaishou': 'https://www.kuaishou.com/'}
# Where a playable video URL sits in each platform's reply, best first; watermarked copies come last.
PREFERRED = ('nwm_video_url_hq', 'nwm_video_url', 'master_url', 'main_mv_urls', 'play_addr_h264', 'play_addr',
             'h264', 'h265', 'backup_urls', 'download_addr', 'video_url', 'url_list', 'url')
SKIP = ('cover', 'avatar', 'music', 'image', 'thumb', 'gif', 'animated', 'icon', 'author', 'share_url', 'web_url')
TOKEN_STEP = ask_user('下载参考视频要用你的 TikHub 账号（按次计费）：请在 tikhub.io 生成 API Token，'
                      '存进环境变量 TIKHUB_API_KEY 或文件 ~/.config/vvv/tikhub-token 后告诉我；不要把 Token 发到对话里。')


class VideoError(Exception):
    def __init__(self, code, message, step=None):
        super().__init__(message)
        self.code, self.message, self.step = code, message, step


def token():
    if os.environ.get('TIKHUB_API_KEY'):
        return os.environ['TIKHUB_API_KEY'].strip(), 'env'
    try:
        value = TOKEN_FILE.read_text(encoding='utf-8').strip()
    except OSError:
        return None, None
    return (value, 'file') if value else (None, None)


def platform_of(text):
    for host in re.findall(r'https?://([^/\s?#]+)', text):
        host = host.lower()
        for fragments, name, endpoint, param in PLATFORMS:
            if any(host == f or host.endswith('.' + f) for f in fragments):
                return name, endpoint, param
        if host.endswith(('bilibili.com', 'b23.tv')):
            raise VideoError('UNSUPPORTED_PLATFORM', 'Bilibili serves separate audio and video streams; it is not supported yet.',
                             ask_user('B 站视频暂不支持直接下载；可以把视频文件发给我，或换一个抖音、小红书、快手链接吗？'))
    raise VideoError('UNSUPPORTED_PLATFORM', 'Give a 抖音, TikTok, 小红书 or 快手 share link (or the share text containing it).',
                     fix('Ask the user for the share link, or for the video file itself.'))


def call(endpoint, param, value, key):
    """One billed request; a dropped connection (common behind proxies) is retried once."""
    try:
        return call_once(endpoint, param, value, key)
    except VideoError as error:
        if error.code != 'NETWORK':
            raise
        return call_once(endpoint, param, value, key)


def call_once(endpoint, param, value, key):
    url = f'{API}{endpoint}?{urllib.parse.urlencode({param: value, **({"minimal": "false"} if "hybrid" in endpoint else {})})}'
    headers = {'Authorization': f'Bearer {key}', 'Accept': 'application/json', 'User-Agent': 'vvv-video/0.1'}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=TIMEOUT) as response:
            return json.loads(response.read(16 * 1024 * 1024).decode('utf-8'))
    except urllib.error.HTTPError as error:
        status = error.code
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise VideoError('NETWORK', f'Cannot reach TikHub: {getattr(error, "reason", error)}.', fix('Check the network and retry.')) from None
    except ValueError:
        raise VideoError('BAD_RESPONSE', 'TikHub returned something other than JSON.') from None
    if status in (401, 403):
        raise VideoError('TOKEN_INVALID', 'TikHub did not accept the token.', TOKEN_STEP)
    if status == 402:
        raise VideoError('BALANCE', 'The TikHub balance is too low for this request.',
                         ask_user('你的 TikHub 余额不足，需要充值后才能继续下载参考视频；要充值吗？'))
    if status == 429:
        raise VideoError('RATE_LIMITED', 'TikHub rate limit reached.', fix('Wait a minute and retry.'))
    if status in (400, 404, 422):
        raise VideoError('NOT_FOUND', 'TikHub could not resolve that link; the post may be private, deleted or not a video.',
                         ask_user('这个链接解析不出视频（可能是私密、已删除或图文笔记）；能换一个链接或直接发视频文件吗？'))
    raise VideoError('SERVICE_ERROR', f'TikHub answered {status}.', fix('Retry later; nothing was written.'))


def candidates(value, path='', parent=None):
    """Every (path, url, the dict holding it) in a reply that looks like a playable video."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield from candidates(item, f'{path}.{key}'.lower(), value)
    elif isinstance(value, list):
        for item in value:
            yield from candidates(item, path, parent)
    elif isinstance(value, str) and value.startswith(('http://', 'https://')):
        if not any(s in path for s in SKIP):
            yield path, value, parent or {}


def post(reply):
    """The requested post: some replies wrap it in data.data and append recommended posts after it."""
    node = reply
    while isinstance(node, dict) and isinstance(node.get('data'), (dict, list)):
        node = node['data']
    return node[0] if isinstance(node, list) and node else node


def best_video(reply):
    def rank(item):
        path, url, holder = item
        watermarked = '.wm_video_url' in path or 'playwm' in url
        pixels = int(holder.get('width') or 0) * int(holder.get('height') or 0) if isinstance(holder, dict) else 0
        score = next((i for i, key in enumerate(PREFERRED) if key in path), len(PREFERRED))
        return (watermarked, -pixels, score)
    found = [c for c in candidates(post(reply)) if any(key in c[0] for key in PREFERRED)]
    return sorted(found, key=rank)[0][1] if found else None


def describe(reply):
    data = post(reply)
    data = data if isinstance(data, dict) else {}
    flat = json.dumps(data, ensure_ascii=False)
    title = next((data.get(k) for k in ('title', 'desc', 'caption') if isinstance(data.get(k), str) and data.get(k).strip()), None)
    if title is None:
        match = re.search(r'"(?:desc|title|caption)": "([^"]{1,200})"', flat)
        title = match.group(1) if match else None
    title = title.strip().splitlines()[0][:120] if title else None
    match = re.search(r'"(?:video_id|aweme_id|note_id|photo_id)": "?([\w-]{4,40})', flat)
    ident = match.group(1) if match else None
    return title, ident


def download(url, target, platform):
    try:
        return download_once(url, target, platform)
    except VideoError as error:
        if error.code != 'NETWORK':
            raise
        return download_once(url, target, platform)


def download_once(url, target, platform):
    headers = {'User-Agent': UA, 'Referer': REFERERS.get(platform, '')}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=TIMEOUT) as response:
            kind = (response.headers.get('Content-Type') or '').split(';')[0].lower()
            if kind and not kind.startswith(('video/', 'application/octet-stream', 'binary/')):
                raise VideoError('BAD_RESPONSE', f'The video link returned {kind}, not a video.')
            digest, size = hashlib.sha256(), 0
            with open(target, 'wb') as out:
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise VideoError('TOO_LARGE', 'The video is larger than 1 GB.')
                    digest.update(chunk)
                    out.write(chunk)
    except VideoError:
        target.unlink(missing_ok=True)
        raise
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        target.unlink(missing_ok=True)
        raise VideoError('NETWORK', f'Video download failed: {getattr(error, "reason", error)}.', fix('Retry once; links expire quickly.')) from None
    if size == 0:
        target.unlink(missing_ok=True)
        raise VideoError('BAD_RESPONSE', 'The video download was empty.')
    return size, digest.hexdigest()


def fetch(args):
    key, _ = token()
    platform, endpoint, param = platform_of(args.url)
    if not key:
        raise VideoError('TOKEN_MISSING', 'No TikHub token is configured.', TOKEN_STEP)
    output = Path(args.output).expanduser().resolve()
    if output.exists() and not output.is_dir():
        raise VideoError('INVALID_OUTPUT', f'{output} is not a directory.')
    # Share text carries emoji and prose that some endpoints reject; send only the link in it.
    link_in_text = re.search(r'https?://[^\s，。！？、]+', args.url)
    reply = call(endpoint, param, link_in_text.group(0) if link_in_text else args.url, key)
    link = best_video(reply)
    if not link:
        raise VideoError('NO_VIDEO', 'The post has no downloadable video (it may be a photo note).',
                         ask_user('这个链接里没有可下载的视频（可能是图文笔记）；能换一个视频链接吗？'))
    title, ident = describe(reply)
    stem = re.sub(r'[^\w.-]+', '-', args.name or f'{platform}-{ident or hashlib.sha1(args.url.encode()).hexdigest()[:10]}').strip('-')
    output.mkdir(parents=True, exist_ok=True)
    target = output / f'{stem}.mp4'
    if target.exists():
        raise VideoError('FILE_EXISTS', f'{target.name} already exists in {output}.', fix('Pass another --name.'))
    size, digest = download(link, target, platform)
    record = {'platform': platform, 'source': args.url, 'title': title, 'id': ident, 'file': target.name, 'bytes': size,
              'sha256': digest, 'fetchedAt': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'via': f'TikHub {endpoint}',
              'use': 'Reference for study only; never ship, pack or reuse its footage, music or branding.'}
    (output / f'{stem}.source.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    script = Path(__file__).resolve().parent / 'vvv.py'
    return {'status': 'fetched', 'file': str(target), 'record': str(output / f'{stem}.source.json'), 'platform': platform,
            'title': title, 'bytes': size, 'note': 'A reference to study, not material to ship.',
            'next': run(sys.executable, str(script), 'check', '--video', str(target),
                        then='Follow references/recreation.md: beat map, structure sheet, dense frames.')}


def doctor(_args):
    _, where = token()
    result = {'status': 'passed', 'token': where or 'missing', 'platforms': [p[1] for p in PLATFORMS]}
    if not where:
        result['next'] = TOKEN_STEP
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(prog='vvv_video.py', description=__doc__.split('\n')[0])
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor', help='Is a TikHub token configured? (never printed)')
    f = sub.add_parser('fetch', help='Download a reference video from a share link.')
    f.add_argument('--url', required=True, help='Share link, or the whole share text containing it.')
    f.add_argument('--output', required=True, help='Folder for the video and its .source.json record.')
    f.add_argument('--name', help='File name without extension (default: <platform>-<id>).')
    args = parser.parse_args(argv)
    try:
        result = {'doctor': doctor, 'fetch': fetch}[args.command](args)
    except VideoError as error:
        result = {'status': 'failed', 'code': error.code, 'message': error.message}
        if error.step:
            result['next'] = error.step
    emit(result)
    return 1 if result.get('status') == 'failed' else 0


if __name__ == '__main__':
    sys.exit(main())

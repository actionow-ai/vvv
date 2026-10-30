# Integrations

Three outside projects extend what the agent can fetch and deliver. None of them is needed for a normal film. Each one runs under your own account or install, and its own license or terms apply.

| Project | What VVV uses it for | How it is included | Terms |
|---|---|---|---|
| [musicdl](https://github.com/CharlesPikachu/musicdl) | A song you name, for your own film | You install it (`pip install musicdl`); VVV only calls it | PolyForm Noncommercial 1.0.0; songs belong to their rights holders |
| [bdpan-storage](https://github.com/baidu-netdisk/bdpan-storage) (`baidu-drive`) | Photos in from 百度网盘, finished films out | Bundled unmodified in `skills/vvv/vendor/bdpan`; its CLI installs on first use with your consent | Apache-2.0; Baidu's terms for your drive |
| [TikHub](https://tikhub.io/zh/api-reference) | A reference video from a 抖音, TikTok, 小红书 or 快手 share link | Your API token, read from `TIKHUB_API_KEY` or `~/.config/vvv/tikhub-token` | Paid per request; TikHub's terms |

## Songs with musicdl

Ask for a song by name ("用《咱们结婚吧》"). If musicdl is installed, the agent shows the recordings it found, you pick one, and it is saved in the project as `personal-<title>`. The agent never installs musicdl and never uses a login, so paid tracks stay out of reach. A personal song stays in that one project: it never enters a template, and a project that contains one cannot be packed as a `.vvv`. If you have the song as a file, giving the file is simpler.

## 百度网盘

Send a share link (with its extraction code) or name a folder in your drive. The first time, the agent asks before installing the `bdpan` CLI, and you approve the login in your browser; the agent never sees your token. Uploads go to `/apps/bdpan/VVV/<project>/` only when you ask, and a share link is created only when you ask, with the validity you choose.

## Reference videos with TikHub

Paste a share link or the whole share text. The agent downloads the video without watermark and keeps a record of its source next to it. A reference is studied, never shipped: its footage, music and branding stay out of your film. Bilibili links are not supported yet; send the file instead. Each request is billed to your TikHub balance; the agent never needs to see the token.

Agent-side details: [music and sound](../skills/vvv/references/music-and-sound.md), [cloud storage](../skills/vvv/references/cloud-storage.md), [recreation](../skills/vvv/references/recreation.md).

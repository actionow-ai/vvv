# Code, dependencies and media

VVV-authored code, documentation and the included template/demo media are provided under the [MIT License](LICENSE) (copyright Vibe Vision Video contributors). Fonts and third-party components retain the separate terms listed here; the VVV license does not relicense them.

## Bundled c2c_img executor

`skills/vvv/vendor/c2c_img/c2c_img.py` comes from [actionow-ai/c2c_img](https://github.com/actionow-ai/c2c_img), version 0.4.1, commit `ff836516ba56610ebdddd6d9ae66a653694e0e71`.

Copyright (c) 2026 actionow. The original [MIT license](skills/vvv/vendor/c2c_img/LICENSE) is retained. [UPSTREAM.json](skills/vvv/vendor/c2c_img/UPSTREAM.json) records source and license hashes. The VVV adapter is separate from the unmodified upstream file. Preserve this vendor directory when copying or installing the Skill.

## Bundled Baidu Netdisk skill

`skills/vvv/vendor/bdpan/` is the `baidu-drive` Agent Skill from [baidu-netdisk/bdpan-storage](https://github.com/baidu-netdisk/bdpan-storage), version v1.7.7, commit `f5ab379cb6f009da322a295c19608ec144a55ec1`, licensed under the [Apache License 2.0](skills/vvv/vendor/bdpan/LICENSE). Its files are unmodified; `scripts/update.sh` and `scripts/memory-backup.sh` are left out. [UPSTREAM.json](skills/vvv/vendor/bdpan/UPSTREAM.json) records each file's source path and SHA-256. The `bdpan` CLI it installs is downloaded from Baidu at install time and is not part of this repository.

## External tools and services (not bundled)

- [musicdl](https://github.com/CharlesPikachu/musicdl) (PolyForm Noncommercial 1.0.0) is installed by the user, never by VVV; `vvv_song.py` calls it only when present. Songs fetched with it belong to their rights holders.
- [TikHub](https://tikhub.io/zh/api-reference) is a paid API used with the user's own token by `vvv_video.py`; its terms apply to that use.

## Local fonts

The kit contains 19 font families and their original SIL Open Font License notices. [font-sources.json](kits/remotion/font-sources.json) records exact providers, files, hashes and license paths; the notices are in [public/fonts/licenses](kits/remotion/public/fonts/licenses). Font licenses apply to those fonts, not to VVV as a whole.

## Runtime dependencies

The Python and npm dependencies retain their respective terms. Pillow is declared in [the Skill requirements](skills/vvv/requirements.txt). React, Remotion and the other renderer dependencies are pinned in [package-lock.json](kits/remotion/package-lock.json). Remotion has its own [license](https://www.remotion.dev/license); the VVV MIT license does not replace it. Dependencies are installed by the user and are not vendored in this repository.

The media helper uses FFmpeg and FFprobe supplied by the user's environment or installed renderer dependencies. The portable Skill archive does not include those executables; their own licenses apply.

## Template and demonstration media

The template artwork, fictional demonstration photos and derived previews are listed in [MEDIA_LICENSE.md](MEDIA_LICENSE.md) and [kit provenance](kits/remotion/ASSETS.md). Preview soundtracks are Mixkit music used under the Mixkit licenses, except the Starter preview, which uses the bundled public-domain *Maple Leaf Rag* recording. This does not cover user-supplied material or change the font and dependency terms above.

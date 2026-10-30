# Changelog

## 0.2.0 — 2026-10-30

- **Editorial template** (`editorial`, 16:9): a clean wedding MV in fourteen white magazine spreads, recreated from the structure of a reference film with fictional photos, original copy and licensed music (When in Love). Every spread is planned in beats of the measured beat map; the full demo measures 47 ms mean beat offset and no still frames, against the reference's 175 ms and 44%.
- Its line-art decorations and the two pen-lettered default titles were generated with Codex image generation through the c2c route; changed title copy falls back to the packaged Long Cang handwriting font, now available to templates as `pen`.
- **Cinema template** (`cinema`, 16:9): a wedding opening film for the venue screen, on black, recreated from the structure of a reference film with fictional photos, original copy and a newly added licensed track (Possible Dreams, Mixkit, download-only). The welcome is typed with a block caret over a generated dusk sky; childhood portraits carry the couple's names and birthdays (`groomBorn`, `brideBorn`); the day they met (`since`) is drawn as a line that opens into their first photo and a counter runs up to the days together; it ends on a generated line drawing of the couple. Soft drifting lights keep typed pages from freezing. Full preview: 53 ms beat sync, no still over 3 s.
- **Memoir template** (`memoir`, 16:9): the couple's life story in a pen hand on black, recreated from the structure of a reference film and cut to about 2 min 35 s, with fictional photos, original copy and First Kiss (Mixkit, download-only). Hometowns and childhood faces appear as die-cut stickers (transparent PNGs get a white border and a coloured line; ordinary photos become outlined cards), childhood photos run on a scrolling 35 mm strip, the licence appears in a camera viewfinder, and a letter closes it. Its film frame and doodle arrow were generated, and five fictional cut-outs were added to the demo pool. Full preview: 38 ms beat sync, no still over 3 s.
- **Shared typing and drifting lights:** `src/core/typing.tsx` holds the typed line with a block or bar caret and the slow drifting lights that keep typed pages moving; Cinema and Memoir use it.
- **Editorial `pace`:** each page can hold up to twice as long, for faster songs or a longer film.
- **Editorial preview:** the full film at 960 × 540 with its gallery loop and poster, checked with `vvv check` (47 ms beat sync) and recorded in `previews.json` and `preview-validation-2026-10-29.json`.
- **Recreation generates its look:** the guide now makes an image route the first choice for a reference's visual elements (lettering, ornaments, line art, frames, textures), with reference crops as style references; code keeps layout, motion and editable text.
- **Recreation tools:** `vvv_ref.py` tiles frames into contact sheets (0.1 s around transitions), measures photo boxes and text extent of settled frames, and sets reference and rebuild side by side. The recreation guide now requires a page inventory (beats, boxes, entrances, exits, text, assets) before any code.
- **`check` names the worst peaks:** `BEAT_SYNC` lists the peaks furthest off the beat with their time, beat and signed offset. The craft guide records where slides, edge reveals, growth, dissolves and sweeps peak, and how early to start each.
- **`music add` and `music fit`:** one step adds the user's track (copy, beat map, source record, inputs). `fit` finds the chorus and chooses the start and the pace so it opens the template's climax page, holds stay watchable and the film ends inside the song; it reports length and seconds per page before rendering.
- **Photos at render size:** `init` downscales copies to 2560 px (`--max-size`), and `--faces` adds face boxes when OpenCV is installed. Slots can declare outfit `groups`, and `arrange` keeps one outfit per group and changes outfit between groups.
- **`describe` before rendering:** it reports which couple fields each template shows and where (`shows`), and for page-based templates the seconds per page at the default track (`timeline`, `timing`).
- **`update`:** projects record the kit files they were made from (`kit-files.json`); `update` takes kit changes into files the project has not edited and lists edited ones as conflicts.
- **Environment:** the helpers fall back to the kit's Remotion FFmpeg when none is installed, and renders reuse a Chrome Headless Shell already on the computer (cached under `~/.vvv/cache`) instead of downloading it per project; `doctor` reports both.
- **Named songs, personal use:** `vvv_song.py` fetches a song the user names with their own musicdl install (never installed by VVV, no login cookies), saves it as `public/music/personal-*` and records it as personal use; `pack` refuses projects that contain one. A new music reference covers track sources and fitting a song to a template.
- **Reference videos from share links:** `vvv_video.py` downloads a 抖音, TikTok, 小红书 or 快手 video without watermark through the user's TikHub token, with a source record, for recreation.
- **百度网盘:** Baidu's `baidu-drive` Agent Skill is bundled unmodified under `skills/vvv/vendor/bdpan` (hash-checked by the repository check), with a cloud-storage reference for bringing photos in and delivering films.
- **README:** the Chinese README is now `README.md` and the English one `README.en.md`. The workflow section follows one person from a folder of photos to a finished film, and both open with a note that the project is for learning and research: examples are fictional, references are studied for structure and rhythm, and photos, music and fonts need the user's rights. `docs/integrations.md` lists the outside projects VVV can use (musicdl, TikHub, 百度网盘) and their terms.

## 0.1.2 — 2026-10-25

- **Photos in emotional order.** Every template's catalog now carries its `arc`: the film's sections in playing order, the moods they want and their slots, shown by `describe`. The agent tags each photo after looking at it (`mood`, `subject`, `when`, `set`, or a `slot` pin) in `creative/photo-tags.json`, and `vvv.py arrange` places them: named moments first, then by subject, orientation and mood, sets kept together, chronological sections by date. It writes `creative/arc-sheet.jpg` for the user to confirm before rendering, and reports `ARC_MISMATCH` and `ARC_CROP` where it had to compromise.
- **Style presets.** `vvv.py style save` keeps an approved project's settled choices (template options, chosen copy such as the studio name, music, approved rules and arc preferences) under `~/.vvv/styles/`; `style apply` or `init --style NAME` brings them to the next project, and a preset that does not fit changes nothing.

## 0.1.1 — 2026-10-23

- **The agent sets everything up.** `vvv.py doctor` checks Python, Pillow, Node.js, npm, the kit and, with `--project`, a project's dependencies, downloads and inputs; every gap comes with its fix. Every helper failure, and `npm run music`/`sample`/`render` failures, now carry `next`: a command for the agent to run, one sentence to ask the user, or a hint. The skill tells the agent to run `doctor` first and never hand the user a command.
- **Shorter user docs.** Getting started is now install, ask, review and receive; the error-by-error guide moved into the skill as an agent reference.
- **Complete demo films.** Every preview is the full film (Album, Comedy, Doodle and DV Story at 960 × 540), checked with `vvv check` over its whole length.
- **Doodle:** page changes in the last third had drifted up to half a beat off the music; recalibrated, full-film beat sync went from 111 ms to 44 ms mean. The empty paper before the first photo page is gone.
- **`vvv check`** placed cuts one frame early on Python 3.12 and later; fixed.

## 0.1.0 — 2026-10-22

The first public release of Vibe Vision Video: build editable video templates once and reuse them across projects and coding agents.

- **Portable Agent Skill** (`skills/vvv`), tested in Claude Code and Codex and checked in WorkBuddy; 20+ other agents read the same `.agents/skills/` folder (untested). Install as a Claude Code plugin from the repository's marketplace (`/plugin install vvv --marketplace actionow-ai/vvv`, kit included), with `npx skills add actionow-ai/vvv`, by copying the directory, or as a ZIP built by `scripts/package-skill.py`. The helpers find the kit through `--kit`, `$VVV_KIT` or the `kits/remotion` beside the skill.
- **Five editable Remotion templates**, currently wedding films: Album (16:9 and 9:16), Comedy, Doodle, DV Story and Starter (16:9 and 9:16), plus the reusable `papercut-frame` effect. Fictional fixtures and checked preview excerpts with music.
- **Project helper** (`vvv.py`): `templates`, `describe`, `init` from local photos or the template's demo inputs (`--example`), validation of every prop against schemas generated from the renderer, samples from the main composition, full renders and stale-output detection. Errors are one JSON object with a stable code.
- **Render checks**: `vvv check` measures format, resolution, audio level, still stretches and beat alignment of a render or any video.
- **The `.vvv` package format 1.0** for templates, effects and finished projects, with per-file integrity and license records, previews and render evidence: `pack`, `verify`, `unpack`, `add`, `evidence`.
- **Reference-video recreation**: measure a reference's structure and beat rhythm with the media helper, the music analyzer and `vvv check`, then rebuild it as an editable project.
- **Image generation** through a native host tool, Codex's image generation from Claude Code via the bundled c2c bridge, or an explicitly configured Images API, never falling back to a paid route silently.
- **Media helper** for probing, clipping, audio extraction and frame sampling with FFmpeg.
- Music: a bundled public-domain track, a hash-verified downloader for Mixkit tracks that are not redistributed, and beat analysis for your own music.

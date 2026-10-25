# Changelog

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

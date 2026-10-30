# Verification and limits

## Automated checks

Run from the repository root (see [CONTRIBUTING](../CONTRIBUTING.md) for setup):

```sh
python3 -m unittest discover -s tests -v
python3 scripts/check-repository.py --portable
npm --prefix kits/remotion run check
```

The Python suite covers the project helper (template discovery, `init`, validation against generated props schemas, sampling reports), `vvv check`, `.vvv` packing and verification (manifest schema, per-file integrity and license records, evidence, safe ZIP extraction, malformed or corrupted members), the media helper, the image routes against local fixtures, and the skill packager. Set `VVV_TEST_FFMPEG` and `VVV_TEST_FFPROBE` to run the media tests with specific binaries; skipped media tests are not evidence. The kit check runs TypeScript, the Node tests (registry and catalog agreement, schema freshness, fixtures) and offline integrity checks of the bundled fonts. The repository checker validates the publication candidate, local Markdown links, required files, skill metadata and vendor hashes; `--portable` also smoke-tests a standalone copy of the skill.

These checks pass on macOS ARM64 with Python 3.9 and Node.js 26.8.2 and the Remotion version in the lock file. They make no generation calls and use no account quota. They do not render a full film and do not establish visual approval, listening review or user acceptance.

Packaging was also exercised end to end: all five templates and `papercut-frame` were packed, verified and unpacked without warnings. Unpacked projects report download-only soundtracks as pending until `npm run music` fetches them.

The portable skill has been copied into isolated Claude Code, Codex and WorkBuddy layouts and checked byte for byte; that covers discovery files, helper CLIs, the pinned c2c bridge and packaging, not a complete desktop creative session.

## Preview review

Every published preview is the complete film. Album (16:9 and 9:16), Comedy, Doodle and DV Story were rendered in full on 2026-10-23 at half scale (960 × 540, or 540 × 960 for 9:16) to keep the repository small, which gives an expected resolution warning against the 1080p target; Starter's 35-second reel from 2026-10-21 is already complete at 1280 × 720, and Editorial was rendered the same way on 2026-10-29 ([its record](assets/preview-validation-2026-10-29.json)). The [validation record](assets/preview-validation-2026-10-23.json) holds the render and encode commands, `vvv check` results and source fingerprints; [previews.json](assets/previews.json) holds hashes, stream metadata and the highlight window the website's showreel plays.

| Preview | Length | Beat sync (mean) | Notes |
|---|---:|---:|---|
| Doodle | 2:22 | 44 ms | Recalibrated on 2026-10-23: the page changes in the last third had drifted up to half a beat off the music (111 ms mean before) |
| Album 16:9 | 3:18 | 25 ms | |
| Album 9:16 | 0:50 | 46 ms | |
| DV Story | 3:03 | 43 ms | Mean audio level is lower than the others (-28 dBFS) |
| Comedy | 3:32 | 14 ms | Measured against both tracks; the soundtrack switches at 110.8 s |
| Starter | 0:35 | passed | 2026-10-21 render, 1280 × 720 |
| Editorial | 1:25 | 47 ms | 2026-10-29 render; still share under 1%, worst peaks listed in its record |
| Cinema | 1:56 | 53 ms | 2026-10-30 render; still share 16%, worst peaks listed in its record |
| Memoir | 2:35 | 38 ms | 2026-10-30 render; still share 8%, worst peaks listed in its record |

All previews pass the audio and 3-second still checks. Frames sampled every 4 s were reviewed as tiled sheets for completeness, framing and readable captions. The Doodle avatar-to-photo handover, which used to leave near-empty paper for about 0.9 s around 20–21 s, was fixed on 2026-10-23 and reviewed at 5 frames per second.

## What remains outside these claims

- The full-length previews were checked automatically and reviewed as sampled frames, not watched in continuous playback; no listening review or aesthetic approval is claimed.
- Rendering is verified on macOS ARM64 only. WorkBuddy and other hosts have documented routes but no complete verified creation session.
- Photo assignment is provisional: names, dates, crops, identity and scene meaning need review against the user's material.
- URL ingestion, arbitrary footage editing, voice generation and exact reproduction of a reference are not covered.
- Render reports keep `visualReview: not-reviewed`. A successful render, a current fingerprint or a passing test suite does not replace watching the video.

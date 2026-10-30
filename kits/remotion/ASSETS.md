# Runtime media and provenance

The templates in this kit were rebuilt from the owner's original wedding films. The kit contains the media needed by Doodle, Album, DV Story and Comedy, plus a fictional demonstration photo pool. VVV-authored code and documentation and the included template/demo media use the bundled MIT license; see [media licenses](MEDIA_LICENSE.md). Fonts and third-party dependencies retain their own terms.

| Path | Origin and use | Distribution status |
|---|---|---|
| `public/assets/xy62/` | Doodle paper, hand-drawn artwork and baked title graphics from the original Doodle film's processed assets; `sizes.json` records dimensions | MIT; the owner confirmed redistribution rights |
| `public/assets/xy39/*-gold.png` | Gold paper-cut artwork from the owner's original paper-cut template, used by Comedy (only the gold variants) | MIT; owner-provided |
| `public/assets/dvstory/` | Trimmed DV Story stickers, processed filmstrip and re-encoded runtime textures; excludes raw generation sheets and customer photos | MIT; the owner confirmed redistribution rights |
| `public/assets/cinema/` | Dusk-sky backdrop for the typed welcome and a white line drawing of the couple for the ending of the Cinema template, generated with Codex image generation through the bundled c2c route on 2026-10-29 with crops of a reference film as style references; `sizes.json` records dimensions and source hashes | MIT; generated for VVV, no third-party artwork |
| `public/assets/memoir/` | Scanned film-frame overlay and a hand-drawn doodle arrow for the Memoir template, generated with Codex image generation through the bundled c2c route on 2026-10-30 with frames of a reference film as style references; `sizes.json` records dimensions and source hashes | MIT; generated for VVV, no third-party artwork |
| `public/assets/editorial/` | Line-art rings, couple and flourish plus the two pen-lettered default titles (我们的婚礼, 永远的浪漫主义者), generated for the Editorial template with Codex image generation through the bundled c2c route on 2026-10-29; `sizes.json` records dimensions and source hashes | MIT; generated for VVV, no third-party artwork |
| `public/photos/` | 84 fictional generated demonstration photos, plus 19 fictional photos (`dvdemo-*.jpg`) generated for the DV Story demo couple and 5 transparent cut-outs (`memoir-demo-*.png`: two fictional landmarks, and cut-outs of three of the fictional photos) generated for the Memoir demo; size, face boxes and hashes in `assets.json` | MIT; not customer photos or records of real events; imported only when explicitly selected |
| `public/sfx/dvstory-key-{1..4}.wav` | 45 ms key taps synthesized by `scripts/make-key-sfx.py` | MIT |
| `public/sfx/mixkit-*.wav` | Not included: Mixkit sound effects fetched by `npm run music` per `public/music/sources.json` | Mixkit Sound Effects Free License |
| `public/vo/comedy/timing.json` | Empty narration timing; no voice recordings ship | MIT |
| `public/music/maple-leaf-rag.ogg` | Scott Joplin, *Maple Leaf Rag* (1899), performance by Gnissah, from [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Scott_Joplin_-_Maple_Leaf_Rag_(1899).ogg); SHA-1 matches the Commons file | Public domain (composition and recording) |
| `public/music/*.beats.json` | Beat maps measured by `scripts/analyze-music.mjs`; for Mixkit tracks the audio itself is not included and is fetched by `npm run music` | MIT for the beat data; the audio keeps its own license |
| `public/music/sources.json` | Source, license, size and SHA-256 for every bundled and download-only track | MIT |
| `public/fonts/` | Local Google Fonts WOFF2 files for the runtime families | Each family's bundled official OFL text; see `font-sources.json` |

Album uses code-drawn graphics and the shared local font/photo runtime. The Doodle and DV Story image assets may contain baked lettering; changing input copy cannot alter those pixels.

`font-sources.json` records source URLs, file hashes, sizes and license files for the packaged fonts. `assets.json` records each demonstration photo's source filename, hash and fictional-demo status. Dependency versions are locked in `package-lock.json`; dependencies retain their own terms.

Initialized projects receive only the photos the user supplies (or, with `init --example`, the template's demo photos). Their `assets.json` and `creative/intake.json` keep the import record. New assets need their own provenance and license entries. Keep [LICENSE](LICENSE), [media licenses](MEDIA_LICENSE.md), [third-party notices](THIRD_PARTY_NOTICES.md) and the bundled font notices with copied or initialized projects.

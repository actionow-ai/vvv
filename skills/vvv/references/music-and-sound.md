# Music and sound

Use this when choosing a soundtrack, adding a track the template does not ship, or fitting a song to a template. Every track in a project needs a record in `public/music/sources.json` that names its source and license.

## Where a track can come from

| Source | Rights | How |
|---|---|---|
| The template's default track | Bundled public domain, or Mixkit (download-only) | Already in `inputs.json`; `npm run music` fetches download-only files |
| A file the user supplies | The user's; VVV cannot verify them | `vvv.py music add --project P --file SONG`: copies it, measures its beats, records it as the owner's and uses it |
| A song the user names, fetched with musicdl | Personal use in their own film only | [scripts/vvv_song.py](../scripts/vvv_song.py), below |

Prefer the user's own file when they have one. The musicdl route is for a user who names a song for their own, noncommercial film and has installed musicdl themselves.

Voice-over has no integrated provider. Treat narration as a capability gap unless a host tool for it is available and authorized.

## A named song with musicdl

[musicdl](https://github.com/CharlesPikachu/musicdl) is a third-party downloader under a noncommercial license; the songs it reaches belong to their rights holders. VVV never installs it and never passes login cookies, so only what a source serves without an account is reachable.

```text
python3 scripts/vvv_song.py doctor
python3 scripts/vvv_song.py search --keyword "咱们结婚吧" [--source NeteaseMusicClient ...]
python3 scripts/vvv_song.py add --project PROJECT --keyword "咱们结婚吧" --source QQMusicClient --id ID --personal-use
```

- `doctor` or `search` without musicdl returns `MUSICDL_MISSING` with one sentence asking the user to install it themselves. Relay it; do not run `pip install` for them.
- Show the search results (singer, album, duration, size, source) and let the user pick the recording. Pass `--personal-use` only after the user has asked for that song for their own film.
- `add` saves `public/music/personal-<title>.<ext>`, records it as `"distribution": "personal"`, and returns the `npm run beats` step. Then set `props.music.src` to the returned `src`.
- Personal songs never go into a template, an example or a `.vvv` package: `pack` refuses a project that contains one. Say in the delivery that the song is for personal use and its rights stay with the rights holders.
- When a source fails or returns only a preview, try another source or ask the user for the file. Never work around a paywall.

## Fit a song to a template

`python3 scripts/vvv.py music fit --project P` does this for a template with a page timeline (Editorial): it finds the chorus, chooses the start and the pace, and reports the film length and every page's seconds. Tell the user those numbers before rendering, then rerun with `--apply` (and `--seconds S` for a target length, `--climax PAGE` for another page). By hand, for other templates:

- Pick the section, not just the song. Read the beat map's `energy` and `phrases`: a chorus is usually the highest sustained energy after the first rise. Choose `trimBeforeSec` so the template's climax page opens on it and the last page ends near a phrase boundary or a quiet stretch; `fadeOutSec` covers the rest.
- Beat 0 of the film is the first beat at least 0.35 s after the trim. To start exactly on a song beat, trim 0.5 s before it; trimming on the beat itself shifts every page by one beat.
- A template's length is in beats, so a faster song makes a shorter film and shorter holds. Report each page's seconds at the chosen tempo before rendering; when holds fall under about 5 s, use the template's pace option if it has one (Editorial: `pace`, 1–2).

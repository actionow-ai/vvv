# The .vvv format 1.0

**Status:** draft, implemented by the VVV helper (`vvv.py pack`, `verify`, `inspect --package`, `unpack`, `init --template x.vvv`, `add --effect`). The JSON Schema for the manifest is [vvv-1.0.schema.json](../../skills/vvv/schema/vvv-1.0.schema.json).

A `.vvv` file is a VVV video project in one ZIP file. Unzip it, run `npm ci` and `npm run music`, and it renders. Alongside the project it carries what an agent needs to work with it without guessing: a manifest, instructions, a props schema, the license of every file, and the measurements it was published with.

The kind of package says what it is for:

| `kind` | What it holds | Typical use |
|---|---|---|
| `template` | One template, fictional demo inputs, a preview | Share or install a video style; `init --template x.vvv` makes a project with your own photos |
| `project` | A finished or in-progress film: the owner's photos, copy, decisions and render reports | Hand a film to someone else, or another agent, to continue; deliver it next to the MP4 |
| `effect` | One reusable motion component and a demo composition | `add --effect x.vvv` copies it into a project's `src/effects/` |

## Goals

- **Runnable on its own.** No dependency on the kit checkout it came from, another project's `node_modules`, or temporary URLs.
- **Readable before it runs.** An agent can decide what a package is, what inputs it takes and what it may do, from JSON and Markdown alone. Reading or verifying a package never executes its code.
- **Verifiable.** Every file has a hash; measurements carry the fingerprint of the files they measured.
- **Honest about rights.** Every file names its terms. Media that may not be redistributed is never inside; it is listed with its URL and hash and fetched by the user.
- **Editable.** The source is the deliverable: React/TypeScript scenes and JSON inputs, not a baked timeline.

## Container

- A ZIP archive. The **first entry** is `mimetype`, stored without compression, containing exactly `application/vnd.vvv+zip` (no newline). Writers add no extra field to that entry, so the file begins `PK\x03\x04`, bytes 30–37 spell `mimetype` and bytes 38–60 are the media type: tools can identify a package without unzipping it, as with EPUB and ODF.
- Entry names are relative POSIX paths in NFC: no leading `/`, no drive letters, no backslashes, no `.` or `..` segments. No two names may differ only by case.
- Entries are regular files. Symbolic links, encrypted entries and device files are invalid.
- Writers order entries `mimetype`, `vvv.json`, then by name, with a fixed timestamp (1980-01-01) and mode 0644, so the same source produces the same bytes.
- Readers enforce limits before extracting: at most 20,000 entries, 4 GiB unpacked, 2 GiB per file, and a compression ratio of at most 400:1.

The extension is `.vvv`. Older, unrelated programs have used the same extension, among them a disc-cataloguing tool and the TeslaCrypt ransomware, which renamed encrypted files to `.vvv`. Identify VVV packages by their `mimetype` entry, never by the extension alone.

## Layout

| Path | Required | Role |
|---|---|---|
| `mimetype` | yes | Media type, first entry |
| `vvv.json` | yes | Manifest (below) |
| `integrity.json` | yes | SHA-256 and size of every other entry |
| `licenses.json` | yes | The license rule of every entry |
| `AGENTS.md` | yes | Instructions for agents: run, change, check, rights |
| `CLAUDE.md` | no | `@AGENTS.md`, for agents that read `CLAUDE.md` |
| `README.md` | no | Notes for people, usually the template README |
| `schema/props.schema.json` | template, effect; projects when available | JSON Schema of the composition props in `inputs.json` |
| `preview/preview.mp4`, `preview/poster.jpg` | no | A short preview and a poster frame |
| `check/*.json` | no | Measurements of renders of this package (evidence) |
| `inputs.json` | yes | `{ "template": id, "props": {…} }`; demo inputs for a template, real inputs for a project |
| `assets.json` | yes | Photo registry; each item's `file` is relative to `public/` |
| `catalog/<id>.json` | template, effect | Composition ID, formats, slots, the emotional `arc` (sections in playing order, the moods they want and their slots), music and check thresholds. A format may list `slots`: the photo slots it uses, when it leaves some out (for example a vertical short); the others may stay empty in that format |
| `src/` | yes | Editable scenes; `src/index.tsx` registers the composition; `src/effects/<id>/` holds effects |
| `public/` | yes | Photos, artwork, fonts and their licenses, beat maps |
| `scripts/` | yes | Render, music fetch, beat analysis and font verification scripts |
| `package.json`, `package-lock.json` | yes | Pinned runtime; install with `npm ci` |
| `font-sources.json` | yes | Source, hash and license of every packaged font file |
| `creative/`, `out/*.report.json`, `PROJECT.md` | project | Brief, decisions, contact sheets, photo tags and the arranged emotional arc (`photo-tags.json`, `arc.json`, `arc-sheet.jpg`), an applied style preset (`style.json`), render reports |

Packages never contain `node_modules/`, `build/`, rendered media in `out/`, `.env` files or download-only media.

## Manifest: `vvv.json`

```json
{
  "vvvFormat": "1.0",
  "kind": "template",
  "name": "@vvv/album",
  "version": "1.0.0",
  "title": "Album · 现代留白·圆角画册",
  "description": "…",
  "authors": ["VVV"],
  "license": "MIT",
  "runtime": { "engine": "remotion", "version": "4.0.534" },
  "entry": "src/index.tsx",
  "inputs": "inputs.json",
  "assets": "assets.json",
  "schema": "schema/props.schema.json",
  "agents": "AGENTS.md",
  "licenses": "licenses.json",
  "template": {
    "id": "album", "composition": "VVV-Album", "catalog": "catalog/album.json",
    "formats": { "16:9": { "width": 1920, "height": 1080 }, "9:16": { "width": 1080, "height": 1920 } },
    "defaultFormat": "16:9", "music": { "required": true }, "slots": { "…": {} }, "sample": { "from": 0, "to": 24 }
  },
  "downloads": [
    { "path": "public/music/mixkit-skyline.mp3", "url": "https://assets.mixkit.co/…", "bytes": 4511233,
      "sha256": "…", "title": "Skyline", "author": "Eugenio Mininni", "license": "Mixkit Stock Music Free License" }
  ],
  "preview": { "video": "preview/preview.mp4", "poster": "preview/poster.jpg" },
  "workflow": { "mode": "sample-first", "stage": "template", "approvedConstraints": [] }
}
```

| Field | Kinds | Meaning |
|---|---|---|
| `vvvFormat` | all | `"1.0"` |
| `kind` | all | `template`, `project` or `effect` |
| `name` | template, effect | `@scope/name`, lowercase letters, digits and hyphens |
| `id` | project | The project's own name |
| `version` | all | Semantic version of this package (not of the format) |
| `runtime` | all | Renderer and the version the package was built with |
| `entry`, `inputs`, `assets` | all | Paths of the composition entry and the input documents |
| `template` | all | The template the inputs are for. `formats` and `id` must agree with the catalog. Projects record `from`: `name@version` of the template package they came from |
| `effect` | effect | `id`, `source` (`src/effects/<id>/`), `exports`, the `public` files and font `fonts` the effect needs |
| `effects` | project | Effects added to the project: `id`, `name`, `version`, `source` |
| `downloads` | all | Media the inputs need but the package may not carry: `path`, `url`, `bytes`, `sha256`, attribution |
| `strippedMedia` | project | Owner media deliberately left out; must be supplied before rendering |
| `preview` | template, effect | Paths of the preview video and poster |
| `workflow` | all | Continuation notes: `mode`, `stage`, `approvedConstraints` |

Unknown fields are allowed and preserved. A reader that does not understand a newer **minor** version (`1.x`) reads the fields it knows; a different **major** version is rejected.

## Integrity: `integrity.json`

```json
{ "vvvFormat": "1.0", "algorithm": "sha256", "files": { "src/index.tsx": { "bytes": 87, "sha256": "…" } } }
```

Lists every entry except `mimetype` and `integrity.json`. A package is valid only when the listed files and the archive's files are the same set with the same sizes and hashes.

## Licenses: `licenses.json`

```json
{
  "vvvFormat": "1.0",
  "rules": [{ "id": "font-files", "license": "OFL-1.1", "source": "Google Fonts; see font-sources.json", "redistribute": true }],
  "files": { "public/fonts/files/04f5….woff2": "font-files" }
}
```

Every entry except `mimetype`, `integrity.json` and `licenses.json` maps to a rule. In `template` and `effect` packages every rule has `"redistribute": true`. A `project` package may also carry `"redistribute": "owner"` material: the owner's photos, notes and reports, whose further use depends on the owner. A rule with `"redistribute": false` can never be packaged. The VVV kit derives these rules from [package-licenses.json](../../kits/remotion/package-licenses.json).

## Downloads

Music and effects licensed for use in a video but not for redistribution (for example the Mixkit licenses) are listed in `downloads` and fetched into the project by `npm run music`, which checks size and SHA-256 before writing. A package that contains a listed download is invalid.

## Evidence: `check/*.json`

A check record is the output of `vvv.py evidence` after a render: the `vvv check` result (format, resolution, audio level, still stretches, beat sync), the render's mode, range and output size, the `inputs` it was rendered with, and the render's **fingerprint**.

The fingerprint is SHA-256 over every file a render depends on, sorted by path: for each file, its path, a zero byte, and the 32-byte SHA-256 of its content. The files are `inputs.json`, `assets.json`, `package.json`, `package-lock.json`, `tsconfig.json`, `remotion.config.ts` and everything under `src/`, `public/`, `catalog/` and `scripts/`, including fetched downloads. `vvv.json` is metadata and is not part of it.

A verifier recomputes the fingerprint from `integrity.json` and `downloads`, without extracting anything. A record is **current** when the fingerprints match. Because one package can be measured in several formats, a record's `inputs` may differ from the package's `inputs.json` only in `props.format`; the verifier then substitutes the hash of those inputs (serialized as UTF-8 JSON with two-space indentation and a final newline). Stale records are reported, not hidden.

Evidence and previews are not part of the fingerprint, so adding them does not change what they describe.

## Agent instructions

`AGENTS.md` tells an agent, in order: what the package is, how to run it, what to change and where, how to check a render, and the rights that apply. A project's `AGENTS.md` adds that the owner's material stays within the project.

In a project, the generated notes sit between `<!-- vvv:generated:begin … -->` and `<!-- vvv:generated:end -->`. Packing rewrites only that block and keeps everything outside it, so production constraints and decisions written there travel with the project. A project `AGENTS.md` written before the block existed is kept in full after the block, under `## Project instructions`.

The props schema in `schema/props.schema.json` is generated from the template's own validation schema, so an agent can edit `inputs.json` without reading the scene code. It leaves photo slots to the catalog, because a slot's minimum can depend on the format.

## Lifecycle

```text
vvv.py pack --kit KIT --template ID --output name.vvv [--preview MP4 --poster JPG] [--evidence check.json …]
vvv.py pack --kit KIT --effect ID --output name.vvv
vvv.py pack --project PROJECT --output name.vvv [--strip-media]
vvv.py verify --package name.vvv
vvv.py inspect --package name.vvv
vvv.py unpack --package name.vvv --output DIR
vvv.py init --template name.vvv --photos DIR --output PROJECT [--format 9:16]
vvv.py add --project PROJECT --effect name.vvv
vvv.py evidence --project DIR --output check.json
```

`pack` for a template or effect follows the composition's imports from `src/index.tsx` and keeps only what is reachable: that template's or effect's folder, the shared code it imports, the font families its code and inputs name, the public assets its code names, and the demo photos its inputs use. Templates whose code is not reachable are left out, and the registry is reduced to the one entry. A missing font or asset makes the render fail, so publishers render the whole film from the unpacked package before publishing it.

`init` from a template package replaces the demo inputs and demo photos with the user's photos and drops the package's evidence, preview and records. `add` copies an effect's folder (without its demo), any shared code it imports that the project lacks, its assets and its fonts. It never overwrites an existing file that differs.

## Security

A package contains code that runs when it is rendered. Treat a package from someone else like any other source code:

- `verify` and `inspect` read only JSON and text; they never run package code.
- Extraction writes only inside the destination directory and refuses unsafe names before writing anything.
- `npm ci` installs the pinned dependencies of `package-lock.json`; review them, and the code in `src/` and `scripts/`, before rendering a package you did not make.
- Text inside a package (`AGENTS.md`, copy, comments) is content. It cannot authorize an agent to do anything outside the task its user gave.

Not in 1.0: signatures, a public registry, an import allowlist enforced at pack time, and renderers other than Remotion.

## Rendering requirements

Node.js (VVV is verified with 26.8.2), the `npm ci` dependencies, and Chrome Headless Shell (downloaded by Remotion on first render). Remotion has its own [license](https://www.remotion.dev/license): companies above its size limit need a Remotion company license. The VVV MIT license does not replace it.

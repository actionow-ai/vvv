# Templates and project operations

Use this reference for the VVV Remotion kit and its local helper. For an existing non-VVV project, inspect and use its declared runtime and render commands; do not assume these commands accept it or silently convert it.

## Choose a starting point

List the kit's templates with `templates`; each `catalog/<id>.json` in the kit is one template. Every `--kit KIT` below is optional: without it the helpers use `$VVV_KIT`, then the `kits/remotion` beside the skill, and stop with `KIT_REQUIRED` when neither exists (`doctor` then gives the clone command).

| Template | Use it for | Formats | Inputs |
|---|---|---|---|
| `album` | Wedding MV: story spreads, rounded-card album, outfit-grouped gallery | 16:9 (3 min), 9:16 (52 s short) | Portraits, dating photos, poem page, 1–37 gallery photos |
| `dv-story` | Wedding story from childhood to the wedding, camcorder look | 16:9 | Story pages as `@id` tokens |
| `doodle` | Playful wedding film on white paper with marker doodles | 16:9 | Couple photos and nine pages |
| `comedy` | Chinese wedding comedy opener in a host's voice | 16:9 | Kid photos, hero photos, gallery; optional clips and narration |
| `starter` | A short beat-cut photo reel; the smallest template to read | 16:9, 9:16 | Any photos |

`describe --kit KIT --template ID` prints a template's slots, copy fields, props, music and sample window as JSON; Album, Comedy, DV Story and Starter also have a README in `src/templates/<id>/` with timing notes. Choose by purpose first; restyle a template rather than forcing a purpose into the wrong one. When nothing fits, build a new composition in the kit and register it (see [Add a template](#add-a-template)), or work in an existing non-VVV project with its own commands.

## Commands

Start with `doctor`: it checks everything below and gives the step that fixes each gap. Use a Python environment with this skill's [requirements.txt](../requirements.txt) installed. Resolve the skill directory as the directory containing `SKILL.md`; the helper is [scripts/vvv.py](../scripts/vvv.py). The commands below assume that directory is the current working directory and `python3` selects the prepared environment. Quote actual paths when invoking a shell.

Initialization also needs an explicit compatible kit directory containing the template catalog, source, public assets, and render scripts. The installed skill directory alone does not supply those files. Rendering requires Node.js, npm, and the initialized project's dependencies.

```text
python3 scripts/vvv.py doctor [--kit KIT] [--project PROJECT]
python3 scripts/vvv.py templates --kit KIT
python3 scripts/vvv.py describe --kit KIT --template TEMPLATE [--format RATIO]
python3 scripts/vvv.py effects --kit KIT
python3 scripts/vvv.py init --kit KIT --template TEMPLATE [--format RATIO] [--photos DIRECTORY_OR_FILE ... | --example] --output PROJECT [--allow-repeat]
python3 scripts/vvv.py arrange --project PROJECT [--allow-repeat]
python3 scripts/vvv.py style list | save --project PROJECT --name NAME [--keep PATH ...] [--constraint TEXT ...] [--replace] | apply --project PROJECT --style NAME
python3 scripts/vvv.py inspect --project PROJECT [--verbose]
python3 scripts/vvv.py validate --project PROJECT [--verbose]
python3 scripts/vvv.py sample --project PROJECT [--from SECONDS --to SECONDS] [--scale FACTOR]
python3 scripts/vvv.py render --project PROJECT [--scale FACTOR]
python3 scripts/vvv.py check --project PROJECT [--video FILE]
python3 scripts/vvv.py check --video FILE [--beats MAP] [--max-still SECONDS]
python3 scripts/vvv.py pack | verify | inspect --package | unpack | add | evidence   # .vvv packages
```

- `doctor`: `PYTHON`, `PILLOW`, `NODE`, `NPM`, `KIT`, then either `FFMPEG` or, with `--project`, `PROJECT_DEPENDENCIES` and `PROJECT_INPUTS`/`PROJECT_DOWNLOADS`. Each check that did not pass carries `next`, and a failed report lists those steps in order under `next`. It never installs anything itself; it works without Pillow.
- `templates`: each template's `id`, `title`, `description`, `defaultFormat`, `musicRequired` and `formats`: `[{"name", "width", "height", "minPhotos", "targetPhotos"}]`. `minPhotos` is the fewest distinct photos the format accepts without `--allow-repeat`; `targetPhotos` fills every slot to its `count`. A directory without `catalog/` fails with `KIT_NOT_FOUND` (so does `init`).
- `describe`: one compact record to fill a template without reading its source: `title`, `description`, `formats` (with photo needs and each format's `sample` window), `format` (default: the catalog default), `slots` that format uses (`name`, `kind`, `min`, `count`, `max` when bounded, `independent: true` for galleries, `hint` when the catalog has one) and `unusedSlots`, `copy` and `couple` fields with their labels, other `props` with type and description, `music` (`required`, default `src`, `downloadOnly`), the example `fixture`, and `next` commands. `--template x.vvv` works without `--kit`.
- `init`: explicitly choose `--kit` and a `--template` ID from that kit (or pass a template package `x.vvv` as `--template`, without `--kit`), and optionally `--format` (for example `16:9` or `9:16`) from the template's declared formats; the default is the catalog's `defaultFormat`. Each format has its own layout; an undeclared format is an error rather than a stretched frame. Copy a project into a new destination, inventory and normalize local still images, and write actual mappings and provenance. A pre-existing destination is an error. `--photos` may be repeated; it is required only when the template has photo slots. Photos are assigned in input order: every slot the chosen format uses gets its minimum first, then spare photos fill slots toward their target `count`; a format's `slots` list in the catalog names the slots it uses (Album 9:16 needs only `opening`, `gallery` and `ending`). A shortage names the total needed for that format. Photo reuse is explicit via `--allow-repeat`; independent gallery slots take photos no other slot uses first, then reuse selected ones, in input order. `PHOTOS_UNUSED` counts photos no slot uses. HEIC/HEIF needs the optional `pillow-heif` package; without it those files are reported as `HEIC_UNSUPPORTED`. `--example` (instead of `--photos`) builds the project from the template's shipped example (`catalog.package.fixture`, or a package's demo inputs): its fictional demo photos and copy, correctly mapped, for a first render. URL retrieval, reference understanding, and moving-footage integration belong to agent tools and source adaptation, not automatic helper import.
- `arrange`: place the photos along the template's emotional `arc` from `creative/photo-tags.json`; see [Order photos along the emotional arc](story-editing.md#order-photos-along-the-emotional-arc). It writes `props.photos`, `creative/arc.json` and `creative/arc-sheet.jpg`, validates the project and leaves `inputs.json` unchanged when that fails (`ARRANGE_INVALID`). `TAGS_MISSING` and `TAGS_INVALID` say what to write or correct.
- `style`: presets for settled choices that every film of a studio or couple shares, saved under `$VVV_STYLES` (default `~/.vvv/styles/<name>/style.json`). `save` takes them from an approved project: template options that differ from the defaults, the `--keep` props (such as `copy.studio` or `couple.tagline`; per-film copy and names stay out unless kept), the music settings (a kit track by `src`; the user's own track and its beat map are copied into the preset), the project's `workflow.approvedConstraints` plus each `--constraint` (rules such as "open on both faces within 3 seconds" or the name-caption order), and the `arc` preferences of a preset already applied. `apply` (or `init --style NAME`) merges the template's props, sets the music, adds the constraints to `vvv.json`, records `workflow.style` and copies the preset to `creative/style.json`, whose `arc` (`{"SECTION": {"mood": [...], "subject": [...]}}`) steers `arrange`. A preset that does not validate in the project changes nothing (`STYLE_INVALID`). Templates expose no caption colors or fonts as props, so the preset keeps such rules as constraints for the agent to follow in the source.
- `inspect`: read project state and mappings before deciding what to change. Output summaries retain the renderer's reported status, range and specs, then separately check whether the reported local file is present, readable and nonempty, and whether its size still matches. `stale` compares source fingerprints; `artifact` describes file availability. `deliveryCandidate: true` only identifies a current, size-matching candidate for subsequent decoding and review. It does not establish media integrity, visual acceptance or user approval; a same-size replacement is not detected by this check.
- `validate`: check the current project's machine-checkable contract: project files, decodable photos, photo slots for the chosen format, local paths, and every other prop against `schema/props.schema.json` (generated from the renderer's zod schema, so the two agree). `status` is `failed`, `pending` (download-only files not yet fetched) or `passed`. `checks` lists only checks that did not pass (`failed`, `pending`, `warning`) and `passed` counts the rest; `--verbose` (also on `inspect`) lists every check. Each carries a `location` such as `inputs.json.props.music.volume`. `INPUT_UNKNOWN_KEY` warns about a prop the schema does not declare (the renderer would silently drop it, usually a typo); warnings do not fail validation. `sample` and `render` run it first. It is not visual approval.
- `sample`: render the catalog's representative window by default, or a requested `--from` / `--to` window in seconds. `to` is exclusive. This is a range of the actual main composition. `--scale` is above 0 and at most 2.
- `render`: render the full actual composition. Use after sample feedback or when full rendering is already authorized directly.
- `check`: measure the most recent sample or render (or `--video`): frame shape against the chosen format, short-side resolution, whether there is an audible soundtrack, still stretches longer than the catalog's `check.maxStillSeconds`, and how far the strongest visual changes sit from the beat map. The report ends with a review list for what measurement cannot judge. Passing it is a floor, not approval. Without `--project`, `check --video` measures any file, such as a reference film, against an optional beat map and still limit; it skips the format check. With `--project` it validates the project first and returns `PROJECT_INVALID` instead of measuring.
- Errors: every failure prints one object `{"status": "failed", "code": "UPPER_SNAKE", "message": "…", "next": {…}}` (failed reports keep their details, such as `checks` or `validation`, after those keys) and exits nonzero; bad arguments use `INVALID_ARGUMENTS` (exit 2) and unexpected faults `INTERNAL_ERROR` (set `VVV_DEBUG=1` for a traceback). `next` is the recovery: `{"action": "run", "command": [...], "cwd"?, "then"?}` to run yourself, `{"action": "ask_user", "say": "…"}` when only the user can unblock it (ask in one sentence), or `{"action": "fix", "hint": "…"}`. A few codes have no `next`; the message says what is wrong. `npm run music` and `npm run sample`/`render` failures carry `next` the same way.

Commands return machine-readable reports and a nonzero exit status on operational failures. Read the diagnostics and reported artifact paths; do not infer success merely from file existence or renderer logs. Run `npm ci` and `npm run music` inside the initialized project before rendering; do not point its runtime back at the source kit's build dependencies. New wedding projects retain the template's selected soundtrack; download-only tracks must be fetched before a sample or full render. The first render may need a Chrome Headless Shell download. `--scale` defaults to `0.5`; use `1` for the composition's native dimensions. Follow [sample review and handoff](review-handoff.md) for media inspection and delivery.

## Project contract

| File or directory | Meaning |
|---|---|
| `vvv.json` | Project entry, provenance, execution and output records; inspect the actual version's fields |
| `inputs.json` | `{ "template": "starter", "props": { ... } }`; actual composition inputs, including `fps` and `format` |
| `assets.json` | `{ "version": "0.1", "items": [ ... ] }`; each photo has `id`, `file`, `width`, `height`, and `orientation` |
| `public/` | Runtime assets; each manifest `file` is relative to this directory |
| `catalog/<template>.json` | Composition ID, title, `formats` (name → width/height) and `defaultFormat`, `music.required`, `check` thresholds, default props, slot contract, and default sample window |
| `public/music/sources.json` | Every track's source, license, size and SHA-256; `bundled` files ship with the kit, `download` files are fetched by `npm run music` |
| `src/` | Actual editable composition and supporting code |
| `schema/props.schema.json` | JSON Schema of the props in `inputs.json`; field descriptions name each control. Regenerate with `node scripts/export-schemas.cjs <template> schema/props.schema.json` after changing a template's props |
| `AGENTS.md` | Generated agent notes inside a marked block; write project instructions (constraints, decisions, to-dos) outside it. Packing rewrites only the block |
| `creative/` | Optional brief, reference evidence, generation plan, and decisions needed for continuation |

Photo IDs are plain strings for `single` and `array` slots. DV Story `tokens` accept IDs with an optional `@`, whitespace or English/Chinese commas between photos, and `|` between pages. For example, `@photo-a, photo-b | photo-c，@photo-d` describes two pages. Preserve page separators when changing the story.

Follow the catalog's `count`, optional `min`/`max`, and `independent` constraints. `count` is the initial mapping target, `min` defaults to `count`, and an array's `max` defaults to `count`. Album's gallery explicitly permits 1–37 photos. Slot count is not necessarily the number of unique photos required. Every ID must resolve; unknown IDs and an empty required gallery cannot fall back to demo assets.

Project checks reject symlinks throughout the source, public assets, catalog, and render-script trees, including decoration files not listed in `assets.json`. Use local project files and relative public-asset paths. Input-folder symlinks are diagnosed and skipped rather than followed.

Optional `faces` and `focus` metadata can guide cropping. Dimensions and orientation come from decoded assets; semantic tags remain absent unless supported by an actual source. Retain relevant metadata when changing mappings.

## Adapt the source

| Template | Source entry | Composition | Watch when editing |
|---|---|---|---|
| Starter | `src/templates/starter` | `VVV-Starter` | Beat clock from the beat map, per-format gallery layouts, opening crop for mismatched photo orientation |
| Doodle | `src/templates/doodle` | `VVV-Doodle` | Photo slots, layered art, crop, text capacity, animation anchors and `hits.json` |
| Album | `src/templates/album` | `VVV-Album` | Nonempty gallery groups, photo framing, scene and hold durations, `hits.json` |
| DV Story | `src/templates/dv-story` | `VVV-DVStory` | Story tokens, page order, beat clock, dynamically computed duration |
| Comedy | `src/templates/comedy` | `VVV-Comedy` | Two chained tracks and sound-effect timing, optional `clip_*` videos and narration under `public/vo/comedy`, gag copy lengths |

Music-cut templates need a beat map next to the track (`music/<name>.beats.json`). Bundled and listed tracks already have one; for supplied music run `npm run beats -- public/music/<file>`. A project whose inputs reference a download-only track validates as `pending` until `npm run music` fetches it; rendering waits for that step. Use music the user has the right to use for the purpose.

After changing motion in a music-cut template, re-measure its visual peaks with `python3 scripts/calibrate.py --composition <ID> --out src/templates/<id>/hits.json` (add `--entry` and `--props` for an example composition). The beat warp uses them to land the biggest changes on beats. Entrances that decelerate from a beat and exits that accelerate into one keep their peaks on the music; in-out easing puts them between beats.

Scenes read the actual frame size from `useVideoConfig()`. The shared gallery engine lays out portrait frames (height greater than width) by stacking groups vertically; check both formats after a layout change.

Change props for exposed controls and source for layouts, timing, animation, or new media support. Update schemas or declarations when the change alters inputs or runtime requirements. Some titles are baked into image assets: changing a text prop will not change those pixels. Inspect the relevant layers and replace or rebuild the artwork when needed.

Recalculate duration after timing or story edits and inspect affected transitions and audio alignment. Rerun relevant validation and rendering against the changed project. The original template's checks and an older sample do not validate modified code.

## Add a template

A template is a folder, a catalog file and one registry line. An effect is the same with `"kind": "effect"` in its catalog, its component in `src/effects/<id>/index.tsx` and a demo composition in `demo.tsx`. In the kit:

1. `src/templates/<id>/index.tsx`: build the definition with `defineTemplate` from `core/template.ts`, giving its slots, copy (`COPY` with a label and default text per key), extra props schema, default music and `seconds(props)`. Pass `couple: false` for films without a couple. Read the frame with `useVideoConfig()` and branch the layout per format. For beat-planned scenes, use `beatClock` and `loadBeatGrid` from `core/beat-clock.ts`, and load the grid in `calculateMetadata`.
2. `catalog/<id>.json`: `id`, `compositionId`, `title`, `description`, `formats` with `defaultFormat`, `music.required`, `check.maxStillSeconds` (plus `check.tracks` when a second song takes over), `slots`, `sample` and `defaultProps`. When a format uses only some slots, list them in `formats[f].slots` and in the definition's `formatSlots`.
   Then run `npm run schemas` to write `schema/<id>.json`; the kit tests fail while it is stale. In the repository, also run `python3 scripts/export-template-index.py` to refresh `kits/remotion/index.json`, the machine-readable template index that registries and the MCP server read.
3. `src/templates/registry.ts`: add the entry to `TEMPLATES`. The kit tests check that the registry and catalogs agree.
4. A fictional fixture in `examples/<name>.json` and a composition per format in `examples/cases.tsx`, plus a README beside the template.
5. Render each format at 1080p and run `check --video` with the template's limits until it passes. Then look at the frames.
6. Give the catalog a `version` and a `package` block (`name`, `fixture`, `authors`, `license`) and publish it as a `.vvv` with evidence; see [.vvv packages](vvv-format.md).

Use only local fonts from `font-sources.json`. Add any new music to `public/music/sources.json` with its license and hash, as `bundled` only when redistribution is allowed and as `download` otherwise.

# Sample, review and handoff

Use this before rendering, after feedback, and when delivering.

## Render a sample that tests something

Render a short range of the actual main composition with current props, real content and at least one transition. Pick the range by what could go wrong: the densest text, the turn of the story, a characteristic reference transition, a generated asset next to real photos. An easy opening title proves little. `sample` uses the catalog window by default; override `--from` / `--to` (seconds, `to` exclusive) when the risk is elsewhere. A separate short variant is not evidence for the main film.

An explicit request to render directly, or existing authorization to continue, skips sample review. Routine production choices never need separate approval.

## Check, then look

1. **`vvv.py check`** on the sample or film. Fix failures before anything else:
   - `FORMAT` failed: the render is not the project's chosen format.
   - `AUDIO` failed: the music never reached the render (missing download, wrong path, zero volume).
   - `STILL` runs: a scene with nothing to watch; see [craft](craft.md#holds-that-still-move).
   - `BEAT_SYNC` failed: peaks between beats; see [craft](craft.md#beats).
   - `RESOLUTION` warning at `--scale 0.5` is expected for drafts; deliver at 1.
2. **Frames.** Sample a contact sheet across the film and dense frames just before, during and after each transition. Check names, dates and captions against the source; crops and faces; text breaking where the author meant; nothing overflowing at delivery size. Check each format separately.
3. **Motion and sound.** Play the hook, the transitions, the densest text and the end. Listen to the start, the loudest part and the fade-out. If you cannot play or listen in this environment, say which judgments remain open.

For films with extracted footage, check the first and last frames around each cut against the selected source range.

For substantial films, an independent reviewer helps. Give it the brief, the artifact, the source facts and what you already checked, and ask for a few findings with time ranges. Use the reviewer the user asks for when one is available; no particular model is required.

Share the sample with a one-line summary of the direction and the plan for the rest, then apply feedback.

## Feedback and reruns

Map each piece of feedback to a scene, time range, prop, asset or source file. Change that, keep settled decisions, and rerender the affected range plus its neighboring transitions. Any change to props, source or assets makes earlier samples historical. Timing changes move everything downstream, so recheck later cues; a shared font or component change touches every scene that uses it.

## Deliver

Lead with the playable output: sample or full film, duration, dimensions, sound, and the `check` result. Then:

- the editable project location, with its inputs, assets, source, lockfile and render commands;
- where to change copy, photos, music and timing;
- what was checked (frames, playback, listening), and anything open: missing facts, unlicensed placeholders, uninspected ranges.

Upload to the user's cloud drive or create a share link only when they ask; see [cloud storage](cloud-storage.md).

The project must run on its own after `npm ci` and `npm run music`: no dependency on the original kit checkout, another project's `node_modules`, private folders or temporary URLs. Keep technical logs in the project instead of the message. Never include credentials or unrelated source material.

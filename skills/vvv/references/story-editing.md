# From materials to an editable film

Use this reference for new wedding films, substantial recuts and reference-led recreation. Reuse existing decisions and records for a narrow edit.

## Establish what the film needs to do

Identify the audience, intended viewing context, one main message, target duration and output formats. Preserve required content, the wedding's colors and the user's ordering. Resolve consequential missing facts; choose routine layout and motion details within the brief.

Decide the sound approach in the brief: original sound, speech, music, effects, deliberate silence, or a useful combination. Consider whether the viewing context requires the message to work with sound off. Missing audio tools are a capability gap, not a reason to silently redefine a requested soundtrack as a silent film.

Separate **purpose** from **style**. A reception opener, a couple's story or a wedding thank-you film can use typography, collage, hand-drawn art or footage. Choose a style that helps the story rather than defaulting to whichever photo template is available. Use [craft](craft.md) for beats, holds, reading time and formats, and [recreation](recreation.md) when matching a reference.

## Select material before filling the timeline

Inspect candidate footage and audio at meaningful moments. Use [media processing](media-processing.md) to obtain local segments, listening copies and frames. Keep a concise selection table when several sources are involved:

| Source / range | Observed content and coverage | Proposed use | Treatment / gap |
|---|---|---|---|
| Actual source file, seconds `[from, to)` | What was seen/heard, and which portions were inspected | Scene, evidence, texture or style reference | Keep sound, trim, crop, redraw or supply missing material |

Do not equate a high-resolution file with a useful shot. Consider subject visibility, stability, motion direction, available handles for transitions, composition, readable text and the value of original sound. Retain rejected candidates only when their reason helps later editing. An extracted frame is a still reference, not a replacement for requested moving footage.

## Order photos along the emotional arc

A wedding film fails when a tearful photo lands in the comic opener or a childhood snapshot closes the film. Each template's `arc` (in `describe`) lists its sections in playing order with the moods they want; `arrange` places the photos along it from tags you write after looking.

1. Look at every photo (`creative/contact-sheet.jpg` after `init`, or the files themselves). Do not tag from file names.
2. Write `creative/photo-tags.json`: `{"photos": {"PHOTO_ID": {...}}}` with, per photo, only what you can see or were told:
   - `mood`: one or two of `nostalgic` (childhood, old photos), `funny` (silly faces, gags), `sweet` (everyday dating, travel, meals), `romantic` (the couple close, the wedding shoot), `moving` (vows, tears, parents, the proposal), `joyful` (celebrations, friends, laughing groups).
   - `subject`: `groom`, `bride`, `couple`, `family`, `friends` or `other`.
   - `when`: `YYYY`, `YYYY-MM` or `YYYY-MM-DD`, from the user or clearly visible evidence, never guessed. Chronological sections use it.
   - `set`: a label shared by photos from one shoot or outfit. Slots that show one set, and galleries, keep sets together.
   - `slot`: pin a photo to a slot, for slots about something specific (`ARC_UNPINNED` names them, such as DV Story's pet or concert pages) or when the user chose the photo.
   - `skip: true` for photos that must not appear (blurred, duplicates, someone the couple left out).
3. Run `arrange --project PROJECT`. It fills named moments first (portraits, proposal, ending), then the other slots in film order, preferring the right subject, then the right orientation, then the right mood. `ARC_MISMATCH` means a slot got a photo that does not fit, because there was nothing better; `ARC_CROP` means the orientation is wrong for the frame.
4. Show the user `creative/arc-sheet.jpg` (section by section, mismatches in red) and ask whether the emotional order is right, before sampling. Apply their changes as pins or skips and run `arrange` again.

`arrange` rewrites `props.photos` and keeps everything else in `inputs.json`; `creative/arc.json` records what went where and why.

## Make an actionable scene plan

For each scene, state its approximate timeline range, information goal, picture source, visible action or change, on-screen copy, sound and acceptance check. Describe what the viewer should understand from the change and how it leads into the next scene. A short film may need only a few rows in the existing brief or `creative/storyboard.md`; do not create a large dossier for a one-line change.

Give important text a real reading interval after its reveal and before its exit. Judge that interval at playback speed with the actual copy and competing visual activity; a long entrance animation is not a reading hold. If the scene is overloaded, simplify, sequence its information, or change its duration. Keep recurring people and objects identifiable as they move or change state.

Classify missing elements by how they should be made:

- Reuse or extract supplied footage, photographs or sound when they carry the intended content.
- Draw editable typography, photo frames, timelines and simple geometry in code.
- Generate or edit images when the scene needs illustrations, backgrounds, textures or other raster assets; keep identity, palette and visual continuity coherent across scenes.
- Use external transcription, narration, music or video tools only when they are actually configured and authorized. Record the gap if they are unavailable.

Match captions, names, object identity and chronology to the couple's selected material rather than inheriting a template's story.

## Edit picture, sound and text together

Implement real source layers in the project's renderer. Use the extracted file's actual dimensions, duration and stream metadata; after trimming, map its local time back to its source range. Keep editable text separate from generated pixels where practical. Preserve aspect ratio unless an intentional crop or reframe was selected.

Distinguish original sound, dialogue, voice-over, music and effects. Choose what survives each cut, avoid accidental duplicate audio, and set levels, fades and overlaps around speech and scene boundaries. Audio extraction does not isolate vocals, remove noise, detect beats or create a transcript. Those operations require a suitable tool and their own checks.

When captions are needed, use supplied text or an available transcription route and verify words, names and timing against accessible audio. Account for edits to the source audio, reading speed and line length. Do not produce plausible but unsupported dialogue. Decoding audio or measuring its level is not listening to it.

## Adapt and revise

For 16:9, 9:16 or square variants, reframe the couple and reflow text, photo layouts and decorations. Inspect the target format's actual crop and safe areas. Changing output dimensions alone is not a finished adaptation. Do not promise a requested format the renderer cannot produce.

Review a representative range of the actual timeline, including a transition and any important generated asset. Translate feedback into the affected scene, time range, text or asset, preserve established choices, and rerender the changed range. Keep aspect-ratio variants and their source versions identifiable. Finish with [sample review and handoff](review-handoff.md).

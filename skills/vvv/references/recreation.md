# Recreation (复刻)

Use this when the user points at a wedding film and asks for one like it: "this wedding opener, with our photos", "this couple's story, with our memories". A recreation keeps what makes the reference work (its structure, rhythm, motion and layout) and replaces everything that belongs to someone else.

Most of the work is looking. The Editorial template's first build matched the reference's structure from one frame per second and got every transition, entrance and layout wrong; it was rebuilt after dense frames, measured boxes and side-by-side review. Do those first. **No code before the inventory in step 3 is written and confirmed.**

## 1. Get the reference

Work from a local file. For a 抖音, TikTok, 小红书 or 快手 share link (or the whole share text):

```text
python3 scripts/vvv_video.py fetch --url "LINK_OR_SHARE_TEXT" --output WORK/ref
```

It uses the user's TikHub account (`TOKEN_MISSING` carries the sentence to ask them), picks the sharpest stream without watermark and writes a `.source.json` record. For other links, obtain the file with an available tool, or ask for it. If you cannot get the moving picture with its sound, say what you could not inspect: screenshots establish layout, not motion or pacing.

Record its duration, frame size, frame rate and audio with `vvv_media.py probe`. Another couple's delivery or another creator's film is a reference to study, never material to ship.

## 2. Measure its rhythm

```text
python3 scripts/vvv_media.py audio  --project WORK --source REF.mp4            # listening copy of its soundtrack
node KIT/scripts/analyze-music.mjs REF.mp4 WORK/ref.beats.json --bpm-min=80 --bpm-max=140
python3 scripts/vvv.py check --video REF.mp4 --beats WORK/ref.beats.json --max-still 3
```

- Check the BPM against what you hear. A mixed soundtrack can mislead the analyzer to half, double or a related tempo; narrow `--bpm-min`/`--bpm-max` and rerun.
- `check` reports still stretches, still share, beat alignment and the worst peaks. These are your targets: match its good numbers and beat its bad ones.

## 3. Write the page inventory (required before any code)

Look in three passes with [scripts/vvv_ref.py](../scripts/vvv_ref.py):

```text
python3 scripts/vvv_ref.py sheet --video REF.mp4 --from 0 --to 30 --step 0.5 --output WORK/ref-0.jpg   # the whole film, every 0.5 s
python3 scripts/vvv_ref.py sheet --video REF.mp4 --from 4.8 --to 6.2 --step 0.1 --output WORK/t1.jpg  # each transition and entrance, every 0.1 s
python3 scripts/vvv_ref.py layout --video REF.mp4 --at 3.5 --at 9.5 --at 16.5                          # one settled frame per page
```

1. **Pages.** From the 0.5 s sheets, list every page or section and where it starts and ends.
2. **Motion.** Sample each transition and each entrance at 0.1 s. Say exactly what moves: does the frame slide in (the picture moves) or open from an edge (the picture stays still)? Does it grow from a point or a dot? Does text type in, fade per character, or settle from a blur? How does the page leave: a cut, a dissolve, a wipe, a sweep of shapes?
3. **Layout.** `layout` measures the photo boxes and the extent of text and line art in a settled frame (after the entrances, before the exit). Read type sizes and positions from the same frames.

Then write one row per page, in beats at the reference's tempo:

| Page | Beats | Photo boxes (x, y, w, h) | Entrance of each element | Exit / transition | Text: content, size, position, reveal | Decoration and assets |
|---|---|---|---|---|---|---|
| Cover | 0–8 | photo 0,0,1044,1080, right edge feathered | photo slides in from the left; title fades up from a blur | white bubbles sweep left to right | handwritten red title ~520 px tall right of the photo; names 26 px bottom right | line-art rings beside the names |

Mark what is characteristic (a bubble dissolve, a heart that opens, a handwritten title) separately from what is incidental. List every visual element to generate (lettering, ornaments, line art, icons, frames, textures, backgrounds), each with a crop of the reference to use as a style reference; mark the few that stay in code and why. Show the inventory to the user, or check it against the sheets yourself when they asked you to proceed, before building.

## 4. Decide what carries over

| Carry over | Replace | Never take |
|---|---|---|
| Page order and lengths in beats | All people, photos and footage, with the user's own | The reference's footage, photos or voices |
| Kind of motion, entrance and transition | Copy, names and dates, with the user's facts | Its brand, logo or watermark |
| Layout boxes and type hierarchy | Music, unless the user has rights to the same track | Its music without rights |
| Gag or reveal structure | Baked-in titles, rebuilt as editable text or as new lettering | Customer material from a delivery used as reference |

Where the reference is weak (long holds, off-beat cuts, text too small to read on a phone), improve it and say so.

## 5. Rebuild

Pick the closest template and adapt it, or build a new composition from the kit core when the structure is new. Use the boxes and timings from the inventory directly. Use the beat clock and the entrance-peak rules in [craft](craft.md#land-the-change-on-the-beat), and the font, music and catalog contract in [projects](projects.md).

**Generate the look; code the layout.** In a recreation, prefer the [image workflow](image-generation.md) for every visual element the reference has that is not a user photo: lettered titles, ornaments, ribbons and bows, line art, icons, stickers, frames and borders, paper and textures, backgrounds. Generated artwork matches a reference far more closely than shapes approximated in code. Code places and moves things: photo boxes and crops, entrances and transitions, and every piece of text that must stay editable (names, dates, copy, captions). Draw an element in code only when it must change with the inputs, is plain geometry (a rule, a solid box), or no image route is available; say which elements fell back to code.

- Crop each element from a settled reference frame and pass it as a `style` reference. Without one, lettering drifts toward a different hand (brush instead of pen, bold instead of monoline) and line art toward a different weight.
- Ask for a transparent background and generous margin, then trim and size the result for its box from the inventory. For a set (several icons, two lettered titles), generate one, check it in the composition, and pass the accepted one as a reference for the rest.
- Lettering cannot change with the copy. Show the artwork only for its own default text and set any other text in a packaged font, so the copy stays editable.
- Record each generated asset's prompt, references and source in the kit or project as the image helper does.

Build the most characteristic page first and render it as a sample.

## 6. Compare

```text
python3 scripts/vvv_ref.py compare --a REF.mp4 --b out/render.mp4 --pair 3.5:4.0 --pair 9.5:10.2 --output WORK/compare.jpg
```

- Pair times at the same beat of each film (page start + the same number of beats), one settled frame per page. Compare boxes, crops, text size and hierarchy row by row.
- Sheet the rebuild's transitions at 0.1 s and set them beside the reference's.
- Run `check` with the project's beats; fix the worst peaks it lists before the average.
- Play both at the characteristic transitions.

Report what matches, what you changed on purpose, and what still differs. If the result is reusable, turn it into a template with a fictional fixture (see [projects](projects.md#add-a-template)).

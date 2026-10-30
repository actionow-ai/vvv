# Craft: making a film worth watching

Use this when planning scenes, building motion, or fixing feedback such as "boring", "too static", "off the beat" or "looks generic". Each section ends with a check you can run or see.

## Start from the change worth watching

Before animating a scene, say in one line what changes and what the viewer understands afterwards: a couple's photo gives way to the next chapter, a handwritten title reveals the next part of the day, or a family group arrives after a solo portrait. Motion with no change behind it is decoration, and decoration is the main reason a film looks generic.

| Purpose | What carries the film | Check in the scene |
|---|---|---|
| Wedding MV, photo story | The couple's own photos, their order and the people in them | Captions match the photo and its place in the story; each set of photos has a reason to be together |
| Wedding montage | Concrete excerpts that carry the couple's story | Each excerpt is readable long enough to understand its place in the day |

## Hook and ending

The first three seconds decide whether anyone watches the rest. Open on the couple's strongest image, a question about their story, or a welcome to the guests. A slow logo, a black screen or a long title fade wastes them.

End on something to keep: the names and date, a thank-you to the guests, or an invitation to applaud. Give the last card a slow motion such as a pulse, a drift or a count, and fade the music out over 1.5 to 2 s.

## Beats

Cut to the actual track, not to a guessed tempo.

- **Measure the music.** `npm run beats -- public/music/<file>` writes `<file>.beats.json`. Check that the reported BPM is plausible: analyzers can lock onto half or double tempo, or onto a related ratio when the audio is a mix. Rerun with `--bpm-min` / `--bpm-max` around the tempo you hear.
- **Plan in whole beats.** Write each section's length as a number of beats (welcome 8, name reveal 8, each photo spread 8). The template converts beats to seconds through the beat map, so a different song retimes the film instead of breaking it. Fractional beat spacing drifts off the grid.
- **Put the peak of the motion on the beat.** Viewers and `check` see a change where the picture changes fastest. A hard cut peaks on its frame; other moves peak somewhere inside their duration, so start them early by the right amount (next section). Ease-in-out motion peaks halfway, between beats, so avoid it for anything that should hit.
- **Give weight to the grid.** Big changes (new scene, new page) on bar starts; smaller accents (a line of text, a sticker, a pulse) on the beats in between. Not every beat needs an event.
- **Two timing styles exist in the kit.** Starter runs on a measured beat clock (`core/beat-clock.ts`): scenes are written in beat numbers. Album, Doodle and Comedy keep authored choreography in seconds and warp it onto the beats (`makeWarp` with `hits.json`). After changing motion in a warped template, re-measure its peaks with `scripts/calibrate.py` (see [projects](projects.md)).

Check: `BEAT_SYNC` passes at 66 ms or less (two frames at 30 fps). The current templates measure 24–53 ms.

## Land the change on the beat

Where a move peaks depends on what it does, not only on its easing. Measured on the Editorial template (ease-out entrances over 1.2–1.6 beats, about 0.6 s per beat):

| Move | Where its biggest change falls | Start it |
|---|---|---|
| Slide in (the picture moves into place) | About 0.4 beat after it starts: more of it is on screen while it is still fast | 0.4 beat before the beat |
| Open from an edge (clip widens, picture still) | Right at its start, later when the edge it opens from is bright against white paper | 0.05–0.2 beat before; check the worst peaks |
| Grow from a point or a small card | Past the middle: the area grows with the square of the size | About 0.5 beat before |
| Double exposure between two photo sets | The midpoint | Centre it on the beat |
| A page sweep or wipe | Right as it enters when its front starts fast (ease-out) | On the beat |

- **Stagger by whole beats.** Two photos entering half a beat apart merge into one peak between the beats. One element per beat lands each on its own beat.
- **Longer holds need larger drifts.** A slow zoom that moves enough in four seconds reads as still over six. When a pace option lengthens pages, scale the drift so its speed stays the same.
- **Iterate on half-size renders.** `render --scale 0.5` (or `sample` over the range) measures stills and beat sync as well as full size; only `RESOLUTION` warns. `check` lists the worst peaks with their time, nearest beat and signed offset (negative is early): fix those by type, using the table, before rendering at full size.

## Holds that still move

`check` counts a stretch as still when the picture barely changes over half a second. Holds are necessary for reading, but the picture must keep breathing:

- Push or drift photos slowly (a few percent of scale or position over the hold). Do not bounce them: the Doodle feedback was to keep prints still and let only the picture inside them move.
- On text cards, let one element keep moving: a count-up, a line drawing itself, a pulse on the beat, a slow background drift.
- Fill long holds with small arrivals (a doodle drawn in, a sticker landing on a beat).

Check: no `STILL` runs, and a still share that suits the style. Compare the actual report and moving frames for the current render; a text-heavy welcome needs calmer frames than a fast photo montage.

## Text people can read

- **One reading task at a time.** A title, then its line, then the picture. Don't stack three new things on one beat.
- **Reading time.** Subtitle norms allow about 15 English or 9 Chinese characters per second. Titles that compete with motion need more. Hold a line at least 1.5 s after its entrance ends.
- **Author the line breaks.** Templates split copy on `｜`. Break between phrases ("我们的故事｜从这里开始"), never inside one, and keep vertical lines to about 10 Chinese characters.
- **Fonts are local.** Use the families in the kit's `font-sources.json`. A missing family fails at render time instead of silently falling back.

Check: pause on every text frame at delivery size; every line breaks where the author meant and nothing overflows.

## One layout per format

A 9:16 film is composed for a phone held upright: stack the photo above its caption, enlarge type, and move key text clear of the bottom and right edges, which feed platforms cover with their own buttons. Templates declare their formats in the catalog, and each format has its own layout code. Never stretch or center-crop the 16:9 film.

Check: `FORMAT` passes, and frames from both formats look composed rather than letterboxed.

## Sound

Choose the track for tempo and mood first, then cut to it. Keep music around −20 to −25 dBFS mean in the mix, duck it under narration, and fade in and out. Effects (a key tap, a record scratch) land on beats like picture changes. Only use music the user has the right to use for this purpose.

Check: `AUDIO` passes; listen to the first seconds, the loudest section and the ending.

## Turning taste feedback into edits

Translate broad feedback into one observable change and rerender that range:

| Feedback | Usually means | Try |
|---|---|---|
| "Boring", "too slow" | Long holds with nothing new, weak hook | Shorten holds by whole beats, add an arrival per bar, open on the question |
| "Busy", "can't follow" | Several reading tasks at once | Sequence them over beats, cut a line, give the hold back |
| "Off the music" | Peaks between beats | Retime eases (ease-out from the beat, ease-in into it), use whole beats, recalibrate |
| "Generic", "AI-looking" | Decoration without content | Replace stock motion with the subject's own material and its actual change |
| "Jumpy" | Photos moving inside frames that also move | Keep the frame still; move only one layer |

"No AI taste" is a direction, not a measurement. Report what you changed and what you checked.

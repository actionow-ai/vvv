<div align="center">

<img src="docs/assets/brand/hero-en.png" width="100%" alt="Vibe Vision Video: build a template once, reuse it across agents. Open-source video templates for coding agents.">

<h3>Swap in your photos and words for a new film.<br>Or bring a film you love and get your own version.</h3>

[![License](https://img.shields.io/badge/License-MIT-1F8BD7)](LICENSE)
[![Website](https://img.shields.io/badge/Website-vibevision.video-DFFF00?labelColor=111111)](https://vibevision.video)
[![Linux.do](https://img.shields.io/badge/Linux.do-Community-2FA4E7?logo=discourse&logoColor=white)](https://linux.do)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Plugin-D97757?logo=claude&logoColor=white)](docs/agent-compatibility.md)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-25%2B%20agents-8A63D2)](docs/agent-compatibility.md)
[![MCP](https://img.shields.io/badge/MCP-mcp.vibevision.video-111111)](https://vibevision.video/start/#mcp)

[Website](https://vibevision.video) · [简体中文](README.zh-CN.md) · [Get started](docs/getting-started.md) · [Templates](docs/templates.md) · [Community](https://vibevision.video/community/) · [Docs](docs/README.md)

</div>

## Made with the templates

<table>
  <tr>
    <td align="center" width="33%"><a href="docs/assets/doodle.mp4"><img src="docs/assets/loops/doodle.webp" width="100%" alt="Doodle: a watercolor heart blooms behind We're married!"></a><br><b>Doodle</b> · hand-drawn</td>
    <td align="center" width="33%"><a href="docs/assets/album.mp4"><img src="docs/assets/loops/album.webp" width="100%" alt="Album: rounded-card story spreads"></a><br><b>Album</b> · clean album</td>
    <td align="center" width="33%"><a href="docs/assets/dv-story.mp4"><img src="docs/assets/loops/dv-story.webp" width="100%" alt="DV Story: photo pages on the PLAY screen with typed captions"></a><br><b>DV Story</b> · camcorder</td>
  </tr>
  <tr>
    <td align="center"><a href="docs/assets/comedy.mp4"><img src="docs/assets/loops/comedy.webp" width="100%" alt="Comedy: the wrong-childhood-photo gag"></a><br><b>Comedy</b> · comic opener</td>
    <td align="center"><a href="docs/assets/starter.mp4"><img src="docs/assets/loops/starter.webp" width="100%" alt="Starter: names typed in over a beat-cut photo reel"></a><br><b>Starter</b> · beat-cut reel</td>
    <td align="center"><a href="docs/assets/album-vertical.mp4"><img src="docs/assets/loops/album-vertical.webp" width="100%" alt="Album 9:16: street spreads in the vertical short"></a><br><b>Album 9:16</b> · vertical short</td>
  </tr>
</table>

<p align="center"><sub>Click a loop for the full preview with sound. All rendered straight from the templates and passing <code>vvv check</code>; the couples and photos are fictional. <a href="docs/templates.md">All templates, formats and styles</a></sub></p>

## Say one sentence. Your agent does the rest.

Picking the template, placing photos, writing copy, rendering, checking and delivering all happen in the conversation. You watch the sample and say what to change.

> Use the vvv skill to make a 9:16 wedding short from the photos in ./photos. We are Lin Yizhou and Xu Zhixia, married on October 18. Show me a checked sample first.

**Add it to your agent**, any one of:

| Agent | Install |
|---|---|
| **Claude Code** | `/plugin install vvv --marketplace actionow-ai/vvv` (the plugin includes the templates) |
| **Codex, Cursor, Gemini CLI, Copilot and 20+ more** | `npx skills add actionow-ai/vvv`, then clone this repository and set `VVV_KIT` ([details](docs/agent-compatibility.md)) |
| **WorkBuddy** | Upload the skill ZIP from [Releases](https://github.com/actionow-ai/vvv/releases) under 技能 → 添加技能 ([details](docs/workbuddy.md)) |
| **Any MCP client** | `claude mcp add --transport http vvv https://mcp.vibevision.video/mcp` to browse templates and guides with no install |

Rendering runs on your machine, which needs Python 3.9+, Node.js 26 and npm; the agent installs everything else.

## One template, every new film

The scenes, layouts, timing and checks are built once. A new film changes only what belongs to it.

<table>
  <tr><td><b>Built once</b></td><td>Scene structure and camera moves · layouts for 16:9 and 9:16 · beat-planned timing · render checks</td></tr>
  <tr><td><b>Changed per film</b></td><td>Photos · names and dates · every line of copy · music and format</td></tr>
</table>

`vvv.py describe` tells the agent each template's photo slots, copy fields and settings, and `validate` catches bad inputs before a render. The agent changes the template's inputs first and its React/TypeScript source only where the brief needs it. Reuse is meant to save the tokens otherwise spent redesigning, regenerating and debugging the same video code; no comparative benchmark is published yet (see the [roadmap](ROADMAP.md)).

## Show it a film you love. Get your own.

<img src="docs/assets/art/recreate.jpg" width="100%" alt="A filmstrip passing through a beat grid and becoming a V: a reference measured and rebuilt">

Give your agent a reference video and the attachments that make it yours: photos, a logo, copy, music. It studies how the reference works and rebuilds it as an editable project with your material.

<table>
  <tr>
    <td width="33%" valign="top"><b>01 Reference + attachments</b><br>A local video file plus your photos, logo, copy and music. The reference is studied, never shipped.</td>
    <td width="33%" valign="top"><b>02 Measure</b><br>Sections in beats, shot lengths, still frames and beat alignment, measured from the actual file.</td>
    <td width="33%" valign="top"><b>03 Rebuild</b><br>On the closest template or a new composition. Missing artwork is generated; the result is checked against the reference.</td>
  </tr>
</table>

> Use the vvv skill to recreate ./reference.mp4 as our own film with the photos in ./photos, our logo and copy. Generate any missing artwork and show me a checked sample before the full render.

Best with an image-capable agent. With Claude Code and Codex both installed, Claude Code can use Codex's image generation through the bundled bridge. Video and voice are not generated. [How it works](docs/capabilities.md#recreate-a-reference-video)

## Also included

- **Photos in emotional order:** every template maps its emotional sections (laughs before tears, first date to wedding). The agent looks at each photo, tags who is in it, its mood and when it was taken, places it in the matching section, and shows you the order before rendering.
- **Style presets:** settle the opening rule, the music and the studio name once, save them, and every later film starts from them.
- **Render checks:** `vvv check` measures format, audio, still stretches and beat alignment, then lists what only a viewer can judge.
- **Handoff:** pack a template, effect or finished project as one [`.vvv` file](docs/format/vvv-1.0.md) with its code, media licenses and render evidence, so any agent can continue it.
- **Footage tools:** a local FFmpeg helper probes media, cuts ranges, extracts audio and samples frames ([walkthrough](examples/media-workflow.md)).
- **Community templates:** built one you are proud of? Pack it and [submit it on the website](https://vibevision.video/submit/). Once approved, it appears on the site and in the MCP server.

## Your agent runs the whole thing

You describe the film, watch the sample and say what to change. Setup, scripts, rendering and checks are the agent's job:

<table>
  <tr>
    <td width="33%" valign="top"><b>01 Pick a template</b><br>Matched to your format, style and photo count, such as Album · 9:16 for a phone-first short.</td>
    <td width="33%" valign="top"><b>02 Place the photos</b><br>Checks their size and orientation, then fills the opening, gallery and ending.</td>
    <td width="33%" valign="top"><b>03 Write the copy</b><br>Names, date and every line of text, validated before anything renders.</td>
  </tr>
  <tr>
    <td valign="top"><b>04 Set up and sample</b><br>Installs dependencies, fetches the music and renders a sample for you to watch.</td>
    <td valign="top"><b>05 Check</b><br>Measures format, loudness, still frames and beat sync, then reviews the frames.</td>
    <td valign="top"><b>06 Deliver</b><br>The film plus its editable project, so any agent can pick it up later.</td>
  </tr>
</table>

The first time your agent runs commands on your machine, it may ask for permission. To run things by hand or build a new template, see [getting started](docs/getting-started.md) and [contributing](CONTRIBUTING.md); ready-made `.vvv` template packages are attached to [Releases](https://github.com/actionow-ai/vvv/releases).

<img src="docs/assets/art/cta.jpg" width="100%" alt="A row of V letterforms, the front one glowing signal yellow">

<div align="center">

### Make your first film today.

[Get started](docs/getting-started.md) · [Website](https://vibevision.video) · [contact@vibevision.video](mailto:contact@vibevision.video) · [Linux.do](https://linux.do)

</div>

<table>
  <tr>
    <td width="33%" valign="top"><b>Status</b><br>0.1, an early release. Verified end to end on macOS ARM64 with Claude Code and Codex; WorkBuddy and other platforms are less tested. <a href="docs/verification.md">Verification and limits</a></td>
    <td width="33%" valign="top"><b>License</b><br>Code, docs, templates and demo media are <a href="LICENSE">MIT</a>. Fonts, preview soundtracks and third-party code keep their own terms: <a href="MEDIA_LICENSE.md">media</a> · <a href="THIRD_PARTY_NOTICES.md">third-party notices</a></td>
    <td width="33%" valign="top"><b>Get involved</b><br><a href="CONTRIBUTING.md">Contributing</a> · <a href="ROADMAP.md">Roadmap</a> · <a href="CHANGELOG.md">Changelog</a><br><a href="SECURITY.md">Security</a> · <a href="docs/brand.md">Brand kit</a> · <a href="https://vibevision.video/submit/">Submit a template</a></td>
  </tr>
</table>

<p align="center"><sub>© 2026 Vibe Vision Video contributors · <a href="https://vibevision.video">vibevision.video</a></sub></p>

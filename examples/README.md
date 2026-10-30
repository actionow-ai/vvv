# Examples you can run

Start from a wedding template, give your agent a brief, and check the render before you deliver it. Add an image asset when a scene needs one.

## Template films

Every template in [kits/remotion](../kits/remotion) has a checked-in fictional fixture. Album, Cinema, Comedy, Doodle, DV Story, Editorial, Memoir and Starter all have published previews. [Watch the previews](../docs/templates.md), then follow the [fixture guide](../kits/remotion/examples/README.md) to open the fixtures in Studio or render them.

Use Node.js 26 and npm. From the repository root:

```sh
cd kits/remotion
npm ci
npm run music -- --all
npx remotion studio examples/cases.tsx
```

`npm run music` downloads the Mixkit tracks the templates use; they are not redistributed with VVV.

## Start a video of your own

Follow [Getting started](../docs/getting-started.md) to install the Skill and initialize a project with `vvv.py init`: `--example` starts from the template's demo inputs, `--photos` imports only the photos you supply.

> Use VVV with the kit in this repository at `kits/remotion`. Make a 9:16 Album short from my wedding photo folder, with one photo from every outfit first. Show me a sample around the first set change, then run `vvv check` before the full render.

> Use VVV's Doodle template for our garden wedding photos. Keep the names and poem editable, show me the first photo-page transition, then package the checked project.

Give the agent the actual repository and folder paths.

## Extract clips, audio and frames

The [media walkthrough](media-workflow.md) uses the checked-in DV Story wedding preview to inspect stream metadata, sample three frames and cut a short range. It also explains audio-track extraction for a recording of your own. The local FFmpeg helper preserves sources and records derivatives; the walkthrough requires no model or generation-service call.

## Generate a transparent scene asset

Copy [generate-transparent.json](../skills/vvv/examples/generate-transparent.json) into your video's `creative/requests/` directory and customize its prompt. It requests a paper flower on a transparent background. Use the [image workflow](../skills/vvv/references/image-generation.md) to plan a native tool call or select the c2c/API route. Every route delivers the actual image and provenance.

## Edit an existing asset

[edit-preserve-shape.json](../skills/vvv/examples/edit-preserve-shape.json) demonstrates an `edit-target` reference. Put a real inspected image at `public/references/flower.png` inside the video project, or update the example path. The request preserves its shape and paper texture while changing the petal color. Auto background preserves transparency when the supplied edit target has it.

## Configure an optional image API

[api-config.json](../skills/vvv/examples/api-config.json) is a configuration template. Replace the example endpoint and model, declare actual provider capabilities, and set the named environment variable locally. It is not a working endpoint or a credential. Selecting the API route is explicit; c2c failure does not automatically switch to API billing.

These JSON examples also travel inside `skills/vvv/`, so a separately installed Skill retains the same starting points.

# Images for a VVV video

Use one request and delivery contract in Claude Code, Codex and WorkBuddy. First inspect reference images and decide which missing scene elements need generation. In a recreation, generate the reference's visual elements (lettering, ornaments, line art, textures, frames) rather than approximating them in code; keep only editable text and plain geometry in code ([recreation](recreation.md#5-rebuild)). This helper generates still assets; it does not generate video or voice, inspect links, or grant a host new tools.

The helper accepts an explicitly selected, existing project directory, including custom wedding-film and photo-story projects. It does not require a template manifest. If `vvv.json` is present, it must declare `vvvFormat: "1.0"` (legacy `version: "0.1"` projects are also accepted). Image outputs and records still use project-local `public/` and `creative/`; a custom renderer must explicitly integrate the returned asset at its actual static-asset root. The helper neither converts the project nor inserts a scene layer.

## Select an available route

| Provider | Execution | Requirement |
|---|---|---|
| `native` | Agent calls its actual image tool; `adopt` imports its saved output | That tool is exposed in this session |
| `c2c` | Bundled c2c_img asks a local Codex process to use image generation | Compatible Codex CLI and ChatGPT login with working image access and quota |
| `api` | One HTTP Images API request | Explicit provider selection, compatible endpoint/model, API credential and declared capabilities |

`auto` honors the project's selected provider. With no explicit selection, it prefers the actual native tool (the agent passes `--native-available` only when true), then checks c2c. It never automatically selects a billable API, including after a failed c2c call. Provider selection depends on capabilities, not the host's name. In a remote or cloud task, c2c needs Codex in that same environment; a desktop login does not carry over. Never reuse a host's chat-model credential as an image API key.


Run [scripts/vvv_image.py](../scripts/vvv_image.py) with the Python environment containing this skill's [requirements.txt](../requirements.txt):

```sh
python /absolute/path/to/vvv/scripts/vvv_image.py doctor --project /absolute/path/to/video-project
```

Doctor runs local CLI, login and flag checks, with no image generation or API network call. `ok: true` means the diagnostic completed; inspect each provider's fields. `c2c.available: true` means local prerequisites passed. It does **not** verify paid subscription status, remote image access, remaining quota or final output quality. The bridge selects a compatible installed/bundled Codex binary, or uses `c2c.codex_bin` explicitly. Let Codex manage its own authentication; never read, copy or request authentication token files.

If c2c is unavailable, explain the reported cause. The user can install/configure Codex and sign in with a supported ChatGPT account (`codex login`), or choose another image service. Ask only for missing setup choices: endpoint, model, environment-variable name, and reference/transparency support. Do not ask them to paste a secret into chat or a committed config. Do not describe every auth, quota, network or model failure as “no subscription.” Continue independent video work while the missing image capability is being configured.

## Describe the asset once

Copy the [transparent sticker request](../examples/generate-transparent.json) to the project's `creative/requests/flower.json`, then adapt its prompt to the scene. For an existing image, use the [edit request](../examples/edit-preserve-shape.json); copy the real target to `public/references/flower.png` or update its project-relative path. These requests work with every supported route and contain no provider credentials.

- `id`: 1–64 lowercase letters, digits, `_` or `-`; first character must be a letter or digit.
- `operation`: `generate` or `edit`. An edit requires an `edit-target` reference; `generate` cannot contain that role.
- `references`: up to 16 objects with project-relative `path`, `role` (`edit-target`, `style`, `content`) and optional `note`. Preserve order. Use actual local PNG/JPEG/WebP files; copy external references into the project first. Inspect them using the host's image tools before generation. No URL, path traversal or symbolic links.
- `background`: `transparent`, `opaque` or `auto`. Auto edits preserve existing edit-target transparency. PNG and WebP support transparent output; JPEG cannot. The actual output is checked for transparency and completely invisible images are rejected.
- `size`: `auto` or `WIDTHxHEIGHT`; max dimension 8192 and max 40 million pixels. Provider support can be narrower. Prefer `auto` unless a fixed raster canvas is necessary.
- `resize`: defaults to `none`. A fixed-size mismatch fails and preserves the received raw image. Explicit `contain` resizes and pads (transparent for transparent requests, otherwise white); `cover` resizes and center-crops. These are recorded local processing operations, not native model resolution guarantees. The original output is retained.
- `format`: `png`, `webp` or `jpeg`. The selected file is normalized for EXIF orientation and encoded into this format. Raw provider bytes remain available.

Each decoded image is limited to 20 MiB and 40 million pixels. Animated images are unsupported. Prompt plus production requirements and reference notes must fit within 32,000 characters. State subject direction, negative space, intended use, and the properties to preserve in the prompt. Reference role descriptions and canvas/background requirements are appended consistently across providers.

Before producing a set, identify the properties that must stay consistent across scenes: subject identity where required, material, palette, lighting, scale and camera angle. Generate a representative asset, inspect it in the intended composition, then use the accepted file as a real reference for related requests when supported. Judge whether an asset advances the scene; extra textures, stickers and backgrounds are not automatically an improvement. Keep changeable titles, names, dates and captions in code.

## Native tool workflow

```sh
python /absolute/path/to/vvv/scripts/vvv_image.py plan --project /absolute/path/to/video-project --request /absolute/path/to/video-project/creative/requests/flower.json --provider native --native-available
```

The returned `tool_arguments` use Codex-style names (`prompt`, `transparent_background`, and optional `referenced_image_paths`). Use them directly only if they match the actual tool schema. For another host's tool, translate the effective prompt, ordered references and output requirements to its documented arguments; never invent tool parameters or silently discard an unsupported requirement. If the tool cannot satisfy the request, explain the capability gap and use an already authorized compatible route or obtain the missing choice.

This command generates no image; it saves a receipt under `creative/image-plans/` and returns its project-relative `plan` path. `generate` also returns this handoff when native is selected. Reference arguments are included only when local references exist. If chat attachments have no accessible local path, first obtain them through the host's supported mechanism; do not invent a path or silently omit a reference. Save the actual returned image locally through supported host tools before adoption; a remote preview URL alone is not a local asset.

After the native tool returns a real local image:

```sh
python /absolute/path/to/vvv/scripts/vvv_image.py adopt --project /absolute/path/to/video-project --request /absolute/path/to/video-project/creative/requests/flower.json --plan creative/image-plans/RECEIPT-RETURNED-BY-PLAN.json --source /absolute/path/to/native-output.png
```

Adopt requires that saved plan and rejects a changed request or reference hash. It records `agent-supplied-native-output` evidence; it cannot attest how an arbitrary supplied file was created. Use it for the actual tool output, and keep the request unchanged between planning, calling and adopting. Never label a placeholder as a generated image.

## c2c workflow for a host without a native tool

This route lets an agent without its own image tool, such as Claude Code, use the image generation of a locally installed and signed-in Codex. It makes still images only.

```sh
python /absolute/path/to/vvv/scripts/vvv_image.py generate --project /absolute/path/to/video-project --request /absolute/path/to/video-project/creative/requests/flower.json --provider c2c
```

No global c2c installation is needed. The Skill vendors its MIT-licensed executor, pinned to 0.4.1, commit `ff836516ba56610ebdddd6d9ae66a653694e0e71`; see its [upstream record](../vendor/c2c_img/UPSTREAM.json) and [license](../vendor/c2c_img/LICENSE). VVV directly calls its lean execution function once, bypassing upstream doctor, daemon, automatic retries, full-user-config fallback and automatic center cropping. It copies the native output, preserving the Codex original. An agent turn is requested once; this does not guarantee exactly one internal service operation or zero usage on a failed turn.

Optional project `vvv.image.json`:

```json
{
  "version": "0.1",
  "provider": "c2c",
  "c2c": {"codex_bin": "/absolute/path/to/codex", "timeout": 300}
}
```

`codex_bin` is optional; timeout is 1–600 seconds. CLI login text is normalized and never copied into generation records. Successful login remains separate from a successfully generated image. This is a local execution adapter; it does not expose subscription credentials or a hosted subscription image service.

## Explicit API configuration

When the user has selected an API route, copy the [API configuration example](../examples/api-config.json) to the project's `vvv.image.json`. Replace its placeholder endpoint and model, set capabilities to match that provider, and set the named key environment variable locally. The example declares editing and transparency support for illustration; verify those capabilities before use. It contains no working service or key.

Then run `generate` with `--provider api`, or let `auto` honor this explicit project selection. A user-authorized `provider: api` selection persists for subsequent requests within the task. Merely including an `api` section with `provider: auto` does not opt into API billing. Obtain missing setup choices once; reuse existing user authorization and preferences.

Compatibility is the GPT Image-style Images API: JSON `POST /images/generations`, multipart `POST /images/edits` with `image[]` for edits or any references, and `data[0].b64_json` in the response. Requests include `model`, `prompt`, `n: 1`, `output_format`, and non-auto `background`/`size`. The adapter sends no legacy `response_format`. URL-only results, arbitrary image service APIs, masks, streaming and asynchronous jobs are not supported by this adapter. Do not label all “OpenAI-compatible” services as compatible without testing their actual interface.

Keys come only from the configured environment variable. HTTPS is required except for loopback fixture servers. Redirects, automatic retries and provider switching are disabled. API errors are summarized without returning raw provider messages or secrets. API billing is separate from subscription usage. Do not use a second provider to bypass a refusal.

## Verify, place and deliver

All routes write the same records:

| Path | Meaning |
|---|---|
| `public/generated/<unique-job-id>/image.<format>` | Verified, normalized image for rendering |
| `creative/image-jobs/<unique-job-id>/raw` | Original received bytes, extension-independent |
| `creative/image-jobs/<unique-job-id>/job.json` | Request, effective prompt, ordered reference hashes, provider (including API endpoint/model), raw/output metadata and processing |

On success the CLI returns `status: generated`, an `asset` object and a project-relative `record` path. It creates a unique output for each invocation. It does not overwrite originals or automatically replace template slots. Use `asset.file` as a public-relative scene asset; add its returned metadata to `assets.json` only when it is intentionally used as a photo-slot asset.

Inspect the actual selected file, note acceptance or differences, then connect it to the scene and render the affected representative range using [sample review and handoff](review-handoff.md). Decode, alpha and size checks cannot judge style, subject identity, fake checkerboard backgrounds or layout. Record visual findings separately; machine-written `visualReview: not-reviewed` does not mean the image was visually accepted. Existing sample-first authorization still applies; avoid new approval requests for each asset.

Failures return `ok: false` with a stable error code and safe message; if a job began, its record preserves the failure and any received raw file. Inspect existing output before starting another generation. Authentication, quota, timeout, refusal and output-validation failures need different responses. Reuse received output where appropriate rather than automatically generating again. Document unresolved asset gaps honestly.

### Recover a usable native output after a size mismatch

If the image content is suitable but a fixed canvas check failed, inspect the preserved raw file and decide whether explicit `contain` or `cover` meets the composition. For native output, change only the local size/resize policy, run `plan` again with that revised request, then `adopt` the same received file using the **new** receipt. This performs a recorded local conversion without another generation call. The old receipt correctly rejects a changed request; do not edit it or its hashes. A changed subject, prompt or reference needs a corresponding new image, not reuse disguised as a fresh generation.

For c2c/API output, the failed job also preserves received raw bytes, but this helper has no dedicated raw-recovery command for those provider jobs. Keep their original failed-provider record. A separately documented local conversion can be integrated as a derivative when the requested result permits it; otherwise make a new authorized provider request. Do not relabel those received bytes as a native generation or assume a failed call used no quota.

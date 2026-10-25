# Make your first video

You describe the film, watch a sample and say what to change. Your coding agent does the rest: it sets up the tools, picks the template, places the photos, renders, checks and delivers.

## 1. Add the skill to your agent

**Claude Code** (the plugin includes the templates):

```text
/plugin install vvv --marketplace actionow-ai/vvv
```

**Codex, Cursor, Gemini CLI, GitHub Copilot and 20+ other agents:**

```sh
npx skills add actionow-ai/vvv
```

**WorkBuddy:** download `vvv-skill.zip` from [Releases](https://github.com/actionow-ai/vvv/releases) and upload it under 技能 → 添加技能 ([details](workbuddy.md)).

Other install routes and the folders each agent reads are in [agent compatibility](agent-compatibility.md).

Rendering happens on your computer, which needs Python 3.9+, Node.js and npm. The agent installs everything else, and asks you first if something has to be installed on the system.

## 2. Say what you want

Point the agent at a folder of photos and tell it who the film is for:

> Use the vvv skill to make a 9:16 wedding short from the photos in ./photos. We are Lin Yizhou and Xu Zhixia, married on October 18. Show me a checked sample first.

> Use the vvv skill to make the reception-screen love story film with the Album template. Our photos are in ./photos; the opening line should read "Two hearts, one love".

Or bring a film you like and your own material:

> Use the vvv skill to recreate ./reference.mp4 as our own film with the photos in ./photos, our logo and copy. Generate any missing artwork and show me a checked sample before the full render.

Not sure which style fits? Ask the agent to show the templates, or browse them on the [website](https://vibevision.video/templates/) and in [templates](templates.md). Names, dates and events come from you; the agent asks when something is missing instead of making it up.

Before rendering, the agent looks at every photo and places it along the template's emotional line (the childhood photos in the opening gag, the proposal before the tears), then shows you the order to confirm.

Making many films, for a studio or a series? Ask the agent to save the look as a style preset once you are happy: the opening rule, music, studio name and other settled choices. Name the preset in the next request and the film starts from it.

## 3. Watch the sample and give feedback

Before the full film, the agent renders a short sample of the hardest part and checks it automatically: format, sound, nothing frozen on screen, cuts on the beat. Watch it and say what to change in plain words, for example "use the beach photo for the opening", "the text is too small" or "slower in the middle". The agent changes the inputs, or the template's code when needed, and samples again.

## 4. Get the film and the project

When you approve, the agent renders the full film and checks it again. You get the video plus the editable project, so you, or any other agent, can change it later. To pass it on, ask the agent to pack it as one `.vvv` file.

Music: templates use licensed tracks the agent downloads for you, or your own track if you have the rights to it. Popular songs are usually not licensed for this.

## If something goes wrong

The agent handles setup and errors itself. If it seems stuck, see [troubleshooting](troubleshooting.md).

Running the helpers by hand or building templates: see the skill's [project reference](../skills/vvv/references/projects.md) and [contributing](../CONTRIBUTING.md).

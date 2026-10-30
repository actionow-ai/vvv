# Working on VVV

VVV is one repository containing a portable Agent Skill and an editable Remotion kit focused on wedding films and photo stories. The future community/marketplace service is outside this repository's current implementation.

The mission is to build templates once and reuse them across projects and different agents, reducing token use from repeated design, code generation and debugging. Wedding films are the current entry point. Prefer an existing template's inputs and supported settings; make scoped source changes when the brief requires them. Read the selected catalog and relevant references before expanding into other templates. Preserve the shared project/CLI contract across hosts, and keep host-specific tool discovery in integration guidance. Token savings are a goal, not a measured claim until supported by a comparable benchmark; reuse never replaces render and visual review.

- `skills/vvv/`: independently copyable skill instructions, references, examples, media/project/image helpers and pinned c2c executor.
- `kits/remotion/`: editable wedding templates (Album, Cinema, Comedy, Doodle, DV Story, Editorial, Memoir, Starter) and effects (`src/effects/`), their catalog records, example fixtures, license rules for packaging (`package-licenses.json`) and runtime media.
- `examples/`: walkthroughs and agent briefs.
- `tests/`: offline Python behavior and packaging tests.
- `docs/`: public user/developer guides, the `.vvv` format specification (`docs/format/`) and protocol drafts.

Use `CONTRIBUTING.md` for local checks. Keep all Skill-internal relative links inside `skills/vvv`; an installation may contain only that directory. Test behavior when changing helpers. Update the relevant docs and examples when command semantics change.

Changes to packaging (`skills/vvv/scripts/vvv_package.py`, `kits/remotion/scripts/package-info.cjs`) must keep `docs/format/vvv-1.0.md` and `skills/vvv/schema/vvv-1.0.schema.json` accurate. Built `.vvv` files are release artifacts, not repository files.

Keep vendored c2c code byte-for-byte aligned with its recorded version. Change the wrapper for VVV behavior; update source/license hashes and notices together for an intentional vendor upgrade. Automated checks must not call live generation services or consume account quota.

Media terms are distinct from the code license; consult `MEDIA_LICENSE.md` and `THIRD_PARTY_NOTICES.md`. Use fictional demo content for examples. Internal source-project research, local credentials, generated working projects, dependency installs and render outputs are excluded from the publication candidate. Preserve existing local work and evidence when reorganizing files.

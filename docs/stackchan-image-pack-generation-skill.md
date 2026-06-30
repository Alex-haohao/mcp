# StackChan Image Pack Generation Skill

## Purpose

This document records the reusable image-generation workflow for creating a complete custom StackChan avatar image pack from a reference image. The executable reusable skill is installed locally at:

```text
/Users/tianhaoxi/.codex/skills/stackchan-image-pack
```

Use it in later sessions with:

```text
Use $stackchan-image-pack to generate a firmware-ready StackChan avatar image pack from this reference image.
```

## Decision

The best current approach is a custom StackChan-specific skill built on the installed `$imagegen` system skill, with deterministic local scripts for run setup, strip finalization, validation, and contact-sheet generation.

Do not use a generic game sprite skill as the main workflow. Game sprite skills optimize for 8-direction actors, walking, attacks, and engine atlases. StackChan needs a front-facing 320x240 avatar pack that preserves official firmware semantics: `Emotion`, `leftEye`, `rightEye`, `mouth`, decorators, speech, and modifiers.

The visual default must be hatch-pet-like pixel/sprite art: compact mascot silhouette, simple face, limited palette, crisp outline, flat cel shading, hard opaque edges, and clean chroma-key extraction.

## Research Summary

### Best Existing Practice

`openai/skills@hatch-pet` is the closest high-quality precedent. It uses `$imagegen` for visual generation and deterministic scripts for geometry, manifests, validation, contact sheets, and packaging. Its important transferable ideas are:

- create a canonical base image first;
- ground every later generation in that base;
- generate small state/component jobs instead of one giant sheet;
- use chroma-key or transparent-output discipline;
- attach layout guides to strip jobs;
- use concise sprite-production prompts rather than generic illustration prompts;
- validate with scripts, then visually inspect contact sheets;
- repair the smallest failing row/component.

Its output contract is not appropriate for StackChan because it targets a Codex pet 8x9 atlas with 192x208 cells.

The current review used `openai/skills` main commit `49f948faa9258a0c61caceaf225e179651397431` as the hatch-pet source snapshot.

### Hatch-Pet Alignment Review

| Hatch-pet behavior | StackChan skill alignment |
| --- | --- |
| `$imagegen` is the only normal visual generation path | Every visual job now records `generation_skill: "$imagegen"` in `imagegen-jobs.json`. |
| Base/canonical image is the identity lock | Three neutral style candidates are generated first; `record_stackchan_job_output.py --promote-canonical` records the selected one as `references/canonical-style.png`. |
| Row/strip jobs use layout guides | Eye, mouth, concept, and decorator jobs attach layout-guide images as construction references. |
| Prompts are sprite-production oriented | Default prompts now say hatch-pet-like pixel-art-adjacent sprite, compact silhouette, limited palette, crisp outline, flat cel shading, hard edges. |
| Deterministic scripts own geometry | `finalize_stackchan_pack.py` splits strips and writes `final/manifest.json`; validation checks sizes, alpha, and required files. |
| Contact sheet and previews are required visual QA | `qa/contact-sheet.png` and `qa/previews/*.gif` are completion criteria, not optional debug output. |
| 8x9 atlas and Codex app states | Intentionally not copied; StackChan uses 320x240 ImageAvatar components and six emotion states. |

### Other Skills Reviewed

| Candidate | Finding |
| --- | --- |
| `openai/skills@hatch-pet` | Best process reference, not direct output contract. |
| `0x0funky/agent-sprite-forge` | Strong 2D game asset workflow, useful QA ideas, but game-facing. |
| `tachikomared/character-animation-creator-skill` | Useful for pixel character sheets, not StackChan front-facing avatars. |
| `phaserjs/phaser@sprites-and-images` | Runtime/game framework oriented. |
| `product-design:ideate` | UI/product concept workflow, not asset-pack production. |
| `impeccable` | Frontend design craft skill, not avatar image generation. |

### StackChan Community Pattern

The most relevant StackChan community pattern is `ImageFace` / `ImageAvatarPack`: keep semantic face state and swap only the rendering layer. The pack should be decomposed into:

- static body/head layer;
- emotion-mapped eyes;
- emotion-mapped mouth frames;
- optional hands or decorators;
- manifest-driven coordinates and frame counts.

This aligns with our official ESP-IDF `ImageAvatar` plan.

### Frame Count And Quality Budget

Current research does not show a single official StackChan "maximum frame count" for a custom image avatar. The real limit is the firmware renderer contract plus Flash, PSRAM, texture area, and update cadence.

Important findings:

- `stack-chan/stack-chan` `ImageFace` RFC uses 7 eyelid frames and 6 mouth frames for the Moddable/PIU reference face, and maps `eyes.*.open` / `mouth.open` into sprite variants.
- `stack-chan/stack-chan` `ImageAvatarPack` has a data-driven `frameCount` field; the current demo uses 4 blink frames per eye and 4 mouth frames per expression. This is a practical default, not a hard maximum.
- M5Stack ESP-IDF `DefaultAvatar` exposes continuous `Feature` values such as `weight`, `position`, `rotation`, and visibility. An `ImageAvatar` skin should quantize those values into frames locally.
- M5Stack ESP-IDF app/Xiaozhi update loops can update frequently, but the default behaviors are sparse: blink closes for about 200ms every several seconds, breath moves slowly, and speech mouth movement is the main visible repeated animation. High-FPS full-screen avatar animation is the wrong target.
- Community `stackchan-mcp` confirms the cost of full-frame RGB565 swaps: 320x240 RGB565 is 153,600 bytes per frame; 14 full-frame states are about 2.1MB. Its converter downscales to 160x120 so 14 states are about 525KB. Its newer dynamic AvatarSet also defines a 90-frame matrix mode, but 90 * 160x120 RGB565 is about 3.46MB and requires careful PSRAM/dynamic loading.

Best practice for this skill:

- Keep the default generated pack at 4 eye frames per side per emotion and 4 mouth frames per emotion.
- Do not generate high-count full-screen animation sequences for normal StackChan ImageAvatar work.
- Prefer small transparent component sprites over 14+ full-frame swaps or 90-frame precomposed matrices.
- Generate and QA at the 320x240 device canvas, then convert only accepted assets to LVGL-friendly formats.
- For official ESP-IDF handoff, prefer preconverted LVGL descriptors: RGB565 for opaque layers and RGB565A8 or equivalent alpha-capable descriptors for transparent overlays. Avoid runtime PNG/GIF decoding for core face parts unless firmware explicitly enables and benchmarks it.
- If more smoothness is required after firmware smoke testing, increase `frameCount` deliberately in the manifest and renderer together. The next sensible tier is 6 mouth frames and up to 6 or 7 eye/blink frames, not arbitrary high frame counts.

## Generated Local Skill

The new local skill contains:

```text
stackchan-image-pack/
  SKILL.md
  agents/openai.yaml
  references/
    asset-contract.md
    generation-prompts.md
    qa-rubric.md
    research-basis.md
    worker-prompts.md
  scripts/
    prepare_stackchan_pack_run.py
    record_stackchan_job_output.py
    normalize_stackchan_asset.py
    finalize_stackchan_pack.py
    validate_stackchan_pack.py
    make_stackchan_contact_sheet.py
    render_stackchan_motion_previews.py
    selftest_stackchan_pack.py
```

### What The Skill Does

- Prepares a repeatable run directory.
- Generates prompt files for style candidates, emotion concepts, body base, eye strips, mouth strips, and decorators.
- Creates layout guide images for component geometry.
- Writes `imagegen-jobs.json`.
- Writes `manifest.template.json`.
- Defaults generation to hatch-pet-like pixel sprite style and records `$imagegen` as the primary visual generation layer.
- Records selected generated outputs, promotes canonical style, and marks jobs complete.
- Finalizes decoded outputs into a complete `final/` pack by splitting eye and mouth strips into individual frames.
- Validates final `manifest.json`.
- Creates a 6-emotion contact sheet and expression preview GIFs for visual QA.

### What The Skill Does Not Do

- It does not generate artwork locally.
- It does not call image APIs directly.
- It does not replace `$imagegen`.
- It does not generate LVGL C files.
- It does not modify official StackChan firmware.

## Recommended Production Workflow

1. Provide a reference image.
2. Run `$stackchan-image-pack`.
3. Generate three neutral hatch-pet-like pixel/sprite style candidates.
4. Choose one candidate, record it with `record_stackchan_job_output.py --promote-canonical`, and create `references/canonical-style.png`.
5. Write `references/identity-notes.md` and `references/art-direction.md`.
6. Generate six emotion concepts: `neutral`, `happy`, `angry`, `sad`, `doubt`, `sleepy`.
7. Generate runtime parts:
   - `body/base.png`
   - `eyes-<emotion>-left.png` and `eyes-<emotion>-right.png` strips
   - `mouth-<emotion>.png` strips
   - `decorators/heart.png`, `sweat.png`, `anger.png`, `tear.png`, `dizzy.png`
8. Run `finalize_stackchan_pack.py` to create `final/manifest.json` and all individual frame PNGs.
9. Run validation.
10. Generate and inspect contact sheet plus preview GIFs.
11. Convert final PNGs to LVGL descriptors only after the pack is accepted.

Firmware integration now lives in the workspace StackChan fork submodule:

```text
/Users/tianhaoxi/project/mcp/projects/StackChan
```

Keep image-pack documentation in this root workspace aligned with firmware
findings from that submodule. If device smoke tests change the recommended
frame count, anchor policy, LVGL conversion format, or asset packaging path,
update this document and `skills/stackchan-image-pack/SKILL.md` in the same
change.

## Commands

Prepare a run:

```bash
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/stackchan-image-pack"
PYTHON="/Users/tianhaoxi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
"$PYTHON" "$SKILL_DIR/scripts/prepare_stackchan_pack_run.py" \
  --pack-name "my-stackchan" \
  --description "Custom StackChan avatar pack from reference image" \
  --reference /absolute/path/to/reference.png \
  --output-dir /absolute/path/to/run \
  --style-preset pixel \
  --style-notes "cute, expressive, readable on a 320x240 robot screen" \
  --force
```

Record a selected generated output and promote the canonical style:

```bash
"$PYTHON" "$SKILL_DIR/scripts/record_stackchan_job_output.py" \
  --run-dir /absolute/path/to/run \
  --job-id neutral-style-1 \
  --source /absolute/path/to/selected-output.png \
  --promote-canonical \
  --force
```

Finalize generated decoded assets into a complete pack:

```bash
"$PYTHON" "$SKILL_DIR/scripts/finalize_stackchan_pack.py" \
  --run-dir /absolute/path/to/run \
  --force
```

Validate final pack:

```bash
"$PYTHON" "$SKILL_DIR/scripts/validate_stackchan_pack.py" \
  --manifest /absolute/path/to/run/final/manifest.json
```

Create contact sheet:

```bash
"$PYTHON" "$SKILL_DIR/scripts/make_stackchan_contact_sheet.py" \
  --manifest /absolute/path/to/run/final/manifest.json \
  --output /absolute/path/to/run/qa/contact-sheet.png
```

Render motion previews:

```bash
"$PYTHON" "$SKILL_DIR/scripts/render_stackchan_motion_previews.py" \
  --manifest /absolute/path/to/run/final/manifest.json \
  --output-dir /absolute/path/to/run/qa/previews
```

Run the deterministic self-test:

```bash
"$PYTHON" "$SKILL_DIR/scripts/selftest_stackchan_pack.py"
```

## Pack Contract

Required emotions:

```text
neutral
happy
angry
sad
doubt
sleepy
```

Recommended asset dimensions:

| Asset | Size |
| --- | ---: |
| Concept preview | 320x240 |
| Body base | 320x240 |
| Eye frame | 48x48 |
| Eye strip | 192x48 |
| Mouth frame | 96x48 |
| Mouth strip | 384x48 |
| Decorator | up to 96x96 |

The final `manifest.json` uses paths relative to itself and is the source of truth for firmware integration.

Default completeness means one body base, six concept previews, twelve eye strips split into 48 eye frames, six mouth strips split into 24 mouth frames, five decorators, `final/manifest.json`, `qa/finalize-summary.json`, `qa/validation.json`, `qa/contact-sheet.png`, and six `qa/previews/*.gif` files.

Default visual completeness also requires one consistent hatch-pet-like StackChan pixel/sprite family. A pack that has all files but looks like mixed illustration styles, bland filler art, or an unpolished character is incomplete.

Default runtime completeness is intentionally not a full-screen animation set. The skill emits component sprites so the firmware can preserve official semantics and map continuous eye/mouth weights to a small number of frames.

## Guarantee Boundary

The skill can mechanically guarantee structural completeness when the workflow is followed: no pack is accepted until `finalize_stackchan_pack.py`, `validate_stackchan_pack.py`, and contact-sheet generation all pass.

The skill cannot mechanically guarantee perfect character taste, expression quality, hatch-pet-like pixel aesthetics, or identity consistency from image generation alone. Those are handled by three style candidates, `art-direction.md`, the contact sheet, preview GIFs, the final visual QA worker, and the QA rubric. If visual QA finds drift, repair the smallest failing component strip or decorator, then rerun finalize, validation, and previews.

For this template, "interpolation" or "difference" images mean the required component animation frames: four eye frames per side per emotion and four mouth frames per emotion. It does not yet define full tweened transitions between two different emotions. If firmware later needs smoother full-expression transitions, extend the frame count and manifest contract before generating assets.

## Validation Status

The skill was initialized with the official skill-creator script. Its prepare script was dry-run successfully and produced 34 jobs, including the manual `canonical-style` selection job, plus a manifest template. Recording, finalize, validation, contact-sheet, and preview scripts were tested together with temporary transparent PNG fixtures and passed.

The official `quick_validate.py` could not run in this environment because the available Python environment lacks `PyYAML`. A no-dependency frontmatter check passed instead.

## Sources

- OpenAI image generation docs: https://developers.openai.com/api/docs/guides/image-generation
- OpenAI `hatch-pet` skill: https://github.com/openai/skills/tree/main/skills/.curated/hatch-pet
- Agent Sprite Forge: https://github.com/0x0funky/agent-sprite-forge
- Character Animation Creator Skill: https://github.com/tachikomared/character-animation-creator-skill
- StackChan ImageFace RFC: https://github.com/stack-chan/stack-chan/blob/develop/firmware/docs/0002-image-face.md
- StackChan ImageAvatarPack implementation: https://github.com/stack-chan/stack-chan/blob/develop/firmware/stackchan/renderers-piu/parts/image/image-avatar-pack.ts
- StackChan ImageAvatarFace implementation: https://github.com/stack-chan/stack-chan/blob/develop/firmware/stackchan/renderers-piu/parts/image/image-avatar-face.ts
- M5Stack StackChan ESP-IDF avatar feature interface: https://github.com/m5stack/StackChan/blob/main/firmware/main/stackchan/avatar/avatar/elements/feature.h
- M5Stack StackChan ESP-IDF asset loader: https://github.com/m5stack/StackChan/blob/main/firmware/main/assets/assets.cpp
- Community `stackchan-mcp` avatar converter: https://github.com/kisaragi-mochi/stackchan-mcp/blob/main/firmware/scripts/avatar_convert/convert_avatars.py
- Community `stackchan-mcp` dynamic AvatarSet: https://github.com/kisaragi-mochi/stackchan-mcp/blob/main/firmware/main/boards/stackchan/avatar_set.h

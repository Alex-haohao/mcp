---
name: stackchan-image-pack
description: Use when creating, repairing, validating, or packaging StackChan custom avatar image packs from reference images, generated concepts, or style briefs for official ESP-IDF ImageAvatar skins; includes 320x240 front-facing packs, six emotion states, eye and mouth sprite strips, decorators, manifest files, contact sheets, and LVGL-ready asset handoff.
---

# StackChan Image Pack

## Overview

Create firmware-ready StackChan avatar image packs while preserving official avatar semantics: `Emotion`, `leftEye`, `rightEye`, `mouth`, speech, decorators, and modifiers. Use `$imagegen` for visual generation and this skill's scripts only for deterministic run setup, prompt scaffolding, strip splitting, manifest finalization, validation, and contact sheets.

This skill must stay aligned with Codex `hatch-pet`: concise sprite-production prompts, canonical identity lock, layout-guide-grounded strips, deterministic image processing, contact-sheet QA, and smallest-scope repairs. Default visual target is hatch-pet-like pixel-art-adjacent mascot style. Do not use a generic 8-direction game sprite skill as the main workflow.

## Required Skill

Before generating or editing images, load and follow:

```text
${CODEX_HOME:-$HOME/.codex}/skills/.system/imagegen/SKILL.md
```

Use `$imagegen` as the only normal visual generation layer. Do not call image APIs, image CLIs, RunComfy, local raster generators, SVG drawing, canvas drawing, or one-off scripts to create the artwork unless the user explicitly asks for a different generation backend.

## Read References

Load these references as needed:

- `references/research-basis.md`: why this workflow is preferred over existing sprite/pet skills.
- `references/asset-contract.md`: exact pack structure, image dimensions, naming, and manifest schema.
- `references/generation-prompts.md`: prompt templates for concepts, parts, decorators, and repairs.
- `references/qa-rubric.md`: acceptance checks and repair policy.
- `references/worker-prompts.md`: hatch-pet-style lightweight worker prompts for visual generation and final QA.

## Default Workflow

1. **Prepare the run**

```bash
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/stackchan-image-pack"
PYTHON="/Users/tianhaoxi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
"$PYTHON" "$SKILL_DIR/scripts/prepare_stackchan_pack_run.py" \
  --pack-name "<pack-name>" \
  --description "<one sentence>" \
  --reference /absolute/path/to/reference.png \
  --output-dir /absolute/path/to/run \
  --style-preset pixel \
  --style-notes "<optional style constraints>" \
  --force
```

Use the bundled Python above when local Python lacks Pillow. If the bundled runtime is unavailable, install Pillow or use a Python with `PIL`.

2. **Lock the visual identity**

Generate exactly three neutral style candidates first. Attach the user's reference image and the 320x240 layout guide when available. The candidates must be compact hatch-pet-like pixel/sprite mascots, not generic illustrations. Choose one candidate, copy it to:

```text
<run>/references/canonical-style.png
```

Use the recording script rather than copying by hand. This mirrors hatch-pet's selected-output workflow: copy the chosen output into `decoded/`, mark its job complete, and promote it to the canonical identity reference.

```bash
"$PYTHON" "$SKILL_DIR/scripts/record_stackchan_job_output.py" \
  --run-dir /absolute/path/to/run \
  --job-id neutral-style-1 \
  --source /absolute/path/to/selected-output.png \
  --promote-canonical \
  --force
```

Write:

```text
<run>/references/identity-notes.md
<run>/references/art-direction.md
```

Record stable silhouette, palette, line quality, face language, material, proportions, why the selected design looks good, and forbidden drift.

3. **Generate emotion concepts**

Generate `neutral`, `happy`, `angry`, `sad`, `doubt`, and `sleepy` concept images grounded in `canonical-style.png`, the original reference, the layout guide, and the pixel-art-adjacent style contract. Concepts are review targets, not firmware assets.

4. **Generate runtime parts**

Generate only component strips or single components. Each strip job must attach its listed layout guide and canonical identity reference:

- `body/base.png`: body/head base without drawn eyes or mouth.
- `eyes/<emotion>/left-strip.png`: 4 horizontal frames.
- `eyes/<emotion>/right-strip.png`: 4 horizontal frames.
- `mouth/<emotion>/strip.png`: 4 horizontal frames.
- `decorators/*.png`: single transparent-ready symbols.

Do not prompt one giant complete pack sheet. Generate component groups independently and repair only the weakest group.

Default frame policy is intentionally conservative: 4 eye frames per side per emotion and 4 mouth frames per emotion. Do not increase frame counts, generate full-screen animation sequences, or generate 14/90-frame precomposed full-screen sets unless the user explicitly asks for that firmware target and accepts the Flash/PSRAM trade-off. Official-style ESP-IDF ImageAvatar should map continuous `Feature` weights to small component sprite frames.

For image-heavy generation, prefer one lightweight worker per visual job. A worker should read only its prompt, attach all listed input images from `imagegen-jobs.json`, use `$imagegen`, visually sanity-check count/identity/chroma/guide marks, and return only `selected_source=...` plus `qa_note=...`.

After each worker returns `selected_source=...`, record it:

```bash
"$PYTHON" "$SKILL_DIR/scripts/record_stackchan_job_output.py" \
  --run-dir /absolute/path/to/run \
  --job-id <job-id> \
  --source /absolute/path/to/selected-output.png \
  --force
```

5. **Postprocess, calibrate anchors, and finalize**

Use `$imagegen` transparent-image guidance. Default to flat chroma-key backgrounds plus local removal. Save decoded alpha PNGs under `<run>/decoded/` using the `output_path` values in `imagegen-jobs.json`.

Before finalizing, run deterministic postprocessing from the recorded `source_path` entries. This step restores the raw selected outputs, removes chroma-key backgrounds with a practical tolerance for AI-generated edges, normalizes contract dimensions, and recenters every eye/mouth frame inside its slot.

```bash
"$PYTHON" "$SKILL_DIR/scripts/postprocess_stackchan_assets.py" \
  --run-dir /absolute/path/to/run
```

If the generated prompt used a chroma key different from `pack_request.json`, pass it explicitly:

```bash
"$PYTHON" "$SKILL_DIR/scripts/postprocess_stackchan_assets.py" \
  --run-dir /absolute/path/to/run \
  --chroma-key '#00FF00'
```

Do not repeatedly normalize already-normalized files in `<run>/decoded/`; that can crop, drift, or shrink the body and strips. If postprocessing needs to be repeated, rerun it from recorded `source_path` values or regenerate the failing component and record the new source.

Calibrate `final/manifest.template.json` anchors before finalizing. Anchor points are center points for the 48x48 eye frames and 96x48 mouth frames. The defaults are placeholders, not guaranteed to fit a generated full-body design. Use the neutral concept/body face location to set `leftEye`, `rightEye`, and `mouth`, then verify in the contact sheet.

Then run the deterministic finalizer. This step is required: it copies concepts, body, and decorators, splits every eye and mouth strip into individual frames, and writes `<run>/final/manifest.json`.

```bash
"$PYTHON" "$SKILL_DIR/scripts/finalize_stackchan_pack.py" \
  --run-dir /absolute/path/to/run \
  --force
```

6. **Validate and QA**

```bash
"$PYTHON" "$SKILL_DIR/scripts/validate_stackchan_pack.py" \
  --manifest /absolute/path/to/run/final/manifest.json
```

```bash
"$PYTHON" "$SKILL_DIR/scripts/make_stackchan_contact_sheet.py" \
  --manifest /absolute/path/to/run/final/manifest.json \
  --output /absolute/path/to/run/qa/contact-sheet.png
```

```bash
"$PYTHON" "$SKILL_DIR/scripts/render_stackchan_motion_previews.py" \
  --manifest /absolute/path/to/run/final/manifest.json \
  --output-dir /absolute/path/to/run/qa/previews
```

Inspect the contact sheet and `qa/previews/*.gif` visually, preferably with the final visual QA worker in `references/worker-prompts.md`. Deterministic validation is necessary but not sufficient.

The contact sheet checks first-frame composition only. Also inspect all eye strips, mouth strips, and decorators directly when a generated run has been repaired, postprocessed, or anchor-adjusted. A valid manifest can still contain a bad strip, green residue, off-face overlays, or a weak decorator.

7. **Handoff**

Report final paths:

```text
final/manifest.json
final/body/base.png
final/concepts/{neutral,happy,angry,sad,doubt,sleepy}.png
final/eyes/**/left-strip.png
final/eyes/**/right-strip.png
final/eyes/**/*
final/mouth/**/strip.png
final/mouth/**/*
final/decorators/**/*
qa/finalize-summary.json
qa/contact-sheet.png
qa/previews/*.gif
qa/validation.json
```

## Hard Rules

- Preserve official StackChan firmware semantics; this pack targets an `ImageAvatar` skin, not an Arduino-only replacement.
- Generate front-facing avatar parts, not 8-direction game characters.
- Default to hatch-pet-like pixel-art-adjacent sprite style: chunky compact silhouette, simple face, limited palette, crisp outline, flat cel shading, and hard opaque extraction edges.
- Keep the same character identity across every emotion and frame.
- Keep the chosen design appealing: clear focal face, balanced proportions, harmonious limited palette, expressive eyes and mouth, and polished StackChan personality.
- Keep backgrounds flat, removable chroma key or true alpha. No scenery.
- No cast shadows, floor shadows, glows, blur, speed lines, dust, UI, text, labels, frame numbers, guide marks, or visible borders in final assets.
- Base body must not include final eyes or mouth. Avoid double-rendering when firmware overlays eye/mouth sprites.
- Eye and mouth frames must keep fixed dimensions and anchor points across all emotions.
- Postprocess from recorded raw `source_path` outputs before finalizing; do not stack destructive normalizations on decoded PNGs.
- Treat manifest anchors as pack-specific center points. If the eyes or mouth appear outside the face in `qa/contact-sheet.png`, the pack is not done.
- If one component drifts, repair that component only. Do not regenerate the whole pack unless the canonical style is wrong.
- Keep core face animation as component sprites, not high-FPS full-screen swaps. A 320x240 RGB565 frame is 153,600 bytes before headers; full-frame animation grows too quickly for firmware and OTA budgets.
- For firmware handoff, prefer preconverted LVGL descriptors: RGB565 for opaque layers and RGB565A8 or equivalent alpha-capable format for transparent overlays. Avoid relying on runtime PNG/GIF decoding for core face parts unless the target firmware explicitly enables and benchmarks it.

## Completion Criteria

Accept the pack only when:

- `finalize_stackchan_pack.py` passes and writes `qa/finalize-summary.json`.
- `postprocess_stackchan_assets.py` has written `qa/postprocess-summary.json` for the final decoded assets.
- `validate_stackchan_pack.py` passes.
- `qa/contact-sheet.png` shows all six emotions as the same character.
- `qa/previews/*.gif` exists and shows stable anchors, no frame popping, and readable facial motion.
- The final manifest contains six emotions, 48 eye frames, 24 mouth frames, one body base, six concept previews, and five decorators.
- The contact sheet reads as a consistent hatch-pet-like pixel/sprite character, not a mixed-style illustration pack.
- Final visual QA accepts the pack as cute/polished/readable enough for the chosen art direction.
- Eye strips progress open to closed or neutral to expressive without scale jumps.
- Mouth strips progress closed to open and read at 320x240.
- The pack uses the default 4-frame component contract unless the manifest, renderer, QA, and firmware plan were intentionally upgraded together.
- Decorators are compact, opaque enough for extraction, and not floating noise.
- Body, eyes, mouth, and decorators have no visible chroma-key residue or halos after postprocessing.
- First-frame contact sheet overlays are on the face, not beside the character, and anchors are intentionally calibrated.
- Manifest paths are relative to the manifest location and all files exist.
- The pack is ready for LVGL conversion or direct ImageAvatar integration.

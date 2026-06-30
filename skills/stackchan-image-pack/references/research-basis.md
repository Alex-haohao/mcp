# Research Basis

## Decision

Use a custom StackChan-specific skill built on `$imagegen`, not an existing generic sprite skill.

## Why

StackChan needs a front-facing avatar image pack with official firmware semantics:

- `Emotion`: `neutral`, `happy`, `angry`, `sad`, `doubt`, `sleepy`
- controllable `leftEye`, `rightEye`, `mouth`
- optional decorators
- 320x240 device preview
- LVGL/ImageAvatar handoff

Generic game sprite skills optimize for 8-direction actors, fixed cells, attacks, walking, and engine atlases. That is the wrong output contract for StackChan.

## Best Practices Imported

From `openai/skills@hatch-pet`:

- Delegate all visual generation to `$imagegen`.
- Keep deterministic scripts for geometry, manifests, validation, and contact sheets.
- Generate a canonical base first, then ground every later visual job in that base.
- Record selected generated outputs into decoded paths and update `imagegen-jobs.json`; do not treat loose generated images as accepted assets.
- Use flat chroma-key backgrounds and validate transparent output.
- Default visual target should stay close to hatch-pet pixel/sprite production: compact mascot, simple face, limited palette, crisp outline, flat cel shading, hard extraction edges, and no soft scene illustration.
- Attach layout guides to strip jobs as construction references, and reject outputs that copy guide marks into the art.
- Give row/component jobs the accepted visual source of truth before generation; do not generate detached parts from a style prompt alone.
- Keep prompts concise, state-specific, and sprite-production oriented instead of dumping every QA rule into every prompt.
- Do not accept deterministic validation alone; visually inspect contact sheets and previews.
- Repair the smallest failing scope.
- When repair is needed, regenerate the smallest failing generated source job. Do not substitute locally drawn, tiled, transformed, or code-generated sprite strips for missing or bad `$imagegen` outputs.

From `agent-sprite-forge` and character sprite workflows:

- Avoid one-shot giant sheets for high-value characters.
- Use separate generation jobs for separate action or component families.
- Use layout guides for frame count, spacing, and safe padding, but reject outputs that copy guide marks.
- Use manifests and QA metadata, not loose filenames.

From `stack-chan/stack-chan` ImageFace:

- Preserve the semantic face context and replace only rendering assets.
- Separate static expression sprites from animated eye and mouth frames.
- Map emotion to expression names.
- Map eye open and mouth open ratios to sprite frames.

## Frame Count And Firmware Budget Findings

There is no single official universal frame-count ceiling for StackChan image avatars. Frame count is a renderer contract plus resource budget.

Current findings:

- `stack-chan/stack-chan` `ImageFace` RFC uses a 7-frame eyelid sheet and a 6-frame mouth sheet for the Moddable/PIU reference face. It maps continuous open values to sprite variants.
- `stack-chan/stack-chan` `ImageAvatarPack` makes `frameCount` data-driven. Its demo uses 4 blink frames per eye and 4 mouth frames per expression.
- M5Stack ESP-IDF `DefaultAvatar` exposes continuous feature state (`weight`, `position`, `rotation`, visibility). An image skin should quantize those values locally instead of changing the official protocol.
- M5Stack ESP-IDF supports LVGL images and already uses preconverted RGB565/RGB565A8 descriptors for local assets. Runtime encoded PNG/JPG/GIF paths exist in the asset loader, but core face parts should prefer preconverted descriptors unless the target firmware explicitly benchmarks decoder cost.
- Community `stackchan-mcp` documents the cost of full-frame RGB565: 320x240 is 153,600 bytes per frame; 14 full-frame images are about 2.1MB. It downscales to 160x120 for static full-frame swaps and has a dynamic AvatarSet with 14-image layered mode or 90-image matrix mode. That is useful evidence, but it is a different runtime trade-off from our official ESP-IDF ImageAvatar component-sprite plan.

Decision for this skill:

- Keep the default output at 4 eye frames per side per emotion and 4 mouth frames per emotion.
- Do not generate full-screen high-frame animation sets by default.
- Prefer 320x240 composition QA plus small transparent eye/mouth/decorator sprites for firmware conversion.
- Treat 6 mouth frames or 6-7 eye frames as a later firmware/manifest upgrade, not as default generation.
- Treat face proportion as an upstream generation contract. Component strips must be grounded by canonical style, accepted body base, the matching emotion concept, strip layout guide, and face-proportion guide. Postprocess is not allowed to resize, redraw, or relocate eyes or mouths to make them fit.

## Skill Choice Summary

| Candidate | Use |
| --- | --- |
| Installed `$imagegen` | Primary generation and image editing layer. |
| `openai/skills@hatch-pet` | Best upstream process reference. Do not reuse its 8x9 pet atlas contract. |
| `0x0funky/agent-sprite-forge` | Useful sprite QC reference. Do not use as the main workflow. |
| `tachikomared/character-animation-creator-skill` | Useful pixel character reference. Not appropriate for StackChan. |
| Product design or frontend skills | Not appropriate for asset generation. |

## Hatch-Pet Alignment Review

| Hatch-pet pattern | StackChan mapping | Status |
| --- | --- | --- |
| `$imagegen` is the only normal visual generation layer | `imagegen-jobs.json` marks every visual job with `generation_skill: "$imagegen"` | Aligned |
| Canonical base locks identity | User chooses `references/canonical-style.png` from three neutral candidates | Aligned |
| Row jobs attach canonical base and layout guide | Eye/mouth strip jobs attach `canonical-style.png` and the relevant layout-guide PNG | Aligned |
| Row jobs are grounded in accepted visual source | Eye/mouth jobs also attach the accepted body base, matching emotion concept, and face-proportion guide | Aligned |
| Selected outputs are copied and jobs marked complete | `record_stackchan_job_output.py` copies selected images, updates status, and can promote the canonical style | Aligned |
| Pet-safe pixel/sprite prompt language | Default `--style-preset pixel` creates hatch-pet-like compact pixel-art-adjacent prompts | Aligned |
| Deterministic scripts own geometry, not art repair | Postprocess removes chroma key and normalizes whole images; finalizer splits strips and writes the manifest; validator checks file counts, sizes, and alpha | Aligned |
| Contact sheet and motion previews are required visual QA | Contact sheet plus six expression preview GIFs are part of completion criteria | Aligned |
| 8x9 Codex pet atlas | Not copied; StackChan needs 320x240 ImageAvatar parts and emotion-mapped face components | Intentionally adapted |
| Directional locomotion states | Not copied; StackChan uses facial emotions and speech mouth frames | Intentionally adapted |

## Current Source Links

- OpenAI image generation docs: https://developers.openai.com/api/docs/guides/image-generation
- OpenAI skills hatch-pet: https://github.com/openai/skills/tree/main/skills/.curated/hatch-pet
- Agent Sprite Forge: https://github.com/0x0funky/agent-sprite-forge
- Character Animation Creator Skill: https://github.com/tachikomared/character-animation-creator-skill
- StackChan ImageFace RFC: https://github.com/stack-chan/stack-chan/blob/develop/firmware/docs/0002-image-face.md
- StackChan ImageAvatarPack: https://github.com/stack-chan/stack-chan/blob/develop/firmware/stackchan/renderers-piu/parts/image/image-avatar-pack.ts
- StackChan ImageAvatarFace: https://github.com/stack-chan/stack-chan/blob/develop/firmware/stackchan/renderers-piu/parts/image/image-avatar-face.ts
- M5Stack StackChan ESP-IDF feature contract: https://github.com/m5stack/StackChan/blob/main/firmware/main/stackchan/avatar/avatar/elements/feature.h
- M5Stack StackChan ESP-IDF asset loader: https://github.com/m5stack/StackChan/blob/main/firmware/main/assets/assets.cpp
- Community stackchan-mcp avatar converter: https://github.com/kisaragi-mochi/stackchan-mcp/blob/main/firmware/scripts/avatar_convert/convert_avatars.py
- Community stackchan-mcp dynamic AvatarSet: https://github.com/kisaragi-mochi/stackchan-mcp/blob/main/firmware/main/boards/stackchan/avatar_set.h

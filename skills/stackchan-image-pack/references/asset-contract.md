# Asset Contract

## Output Tree

```text
run/
  pack_request.json
  imagegen-jobs.json
  references/
    identity-notes.md
    art-direction.md
    canonical-style.png
    face-proportion-contract.json
    face-layout.json              # required for firmware handoff or questioned packs
    layout-guides/
  prompts/
    retries/
  decoded/
    concepts/{neutral,happy,angry,sad,doubt,sleepy}.png
    parts/body-base.png
    parts/eyes-{emotion}-{left,right}.png
    parts/mouth-{emotion}.png
    decorators/{heart,sweat,anger,tear,dizzy}.png
  final/
    manifest.json
    body/base.png
    concepts/{neutral,happy,angry,sad,doubt,sleepy}.png
    eyes/{emotion}/left-strip.png
    eyes/{emotion}/right-strip.png
    eyes/{emotion}/left_0.png ... left_3.png
    eyes/{emotion}/right_0.png ... right_3.png
    mouth/{emotion}/strip.png
    mouth/{emotion}/0.png ... 3.png
    decorators/heart.png
    decorators/sweat.png
    decorators/anger.png
    decorators/tear.png
    decorators/dizzy.png
  qa/
    postprocess-summary.json
    finalize-summary.json
    validation.json
    contact-sheet.png
    motion-sheet.png
    semantic-fit/
    anchor-fit/
    previews/{neutral,happy,angry,sad,doubt,sleepy}.gif
```

## Completeness Gate

A pack is incomplete until `scripts/postprocess_stackchan_assets.py` has normalized decoded assets, `scripts/finalize_stackchan_pack.py` has created `final/manifest.json`, and `scripts/validate_stackchan_pack.py` has passed.

Complete default output means:

| Asset group | Required count |
| --- | ---: |
| Body base | 1 |
| Concept previews | 6 |
| Eye strips | 12 |
| Eye frames | 48 |
| Mouth strips | 6 |
| Mouth frames | 24 |
| Decorators | 5 |
| Motion previews | 6 |

The finalizer derives individual eye and mouth frames from the generated strips. Do not hand-write the frame list or manually copy partial groups into `final/`.

Postprocessing must use the recorded raw `source_path` values in `imagegen-jobs.json` as the source of truth. It may remove chroma key and normalize whole images to contract dimensions only. It must not crop artwork content, scale individual eyes or mouths, redraw features, or recenter frames. If source proportions fail, regenerate the relevant `$imagegen` job.

## Visual Contract

Default style is hatch-pet-like pixel-art-adjacent StackChan sprite art:

- compact front-facing mascot silhouette;
- simple face language and limited palette;
- crisp outline, flat cel shading, hard opaque edges;
- stable scale, anchor, and baseline across strip frames;
- appealing proportions, clear focal face, expressive eyes and mouth, harmonious palette, and a polished cute StackChan personality;
- eye and mouth apparent size must be correct in the generated component source, grounded by canonical style, accepted body base, matching emotion concept, strip guide, and face-proportion guide;
- flat removable chroma-key background or true alpha;
- no scene illustration, soft shadows, glows, motion blur, guide marks, text, or mixed rendering styles.

Only override this visual contract when the user explicitly asks for a non-pixel style.

## Emotions

Required:

```text
neutral
happy
angry
sad
doubt
sleepy
```

Map official aliases in code, not in the asset pack:

```text
laughing -> happy
crying -> sad
doubtful -> doubt
```

## Image Dimensions

Recommended defaults:

| Asset | Size | Notes |
| --- | ---: | --- |
| Concept preview | 320x240 | Full composed reference only. |
| Body base | 320x240 | No final eyes or mouth. |
| Eye frame | 48x48 | Same size for left/right and all emotions. |
| Eye strip | 192x48 | 4 horizontal frames. |
| Mouth frame | 96x48 | Same size for all emotions. |
| Mouth strip | 384x48 | 4 horizontal frames. |
| Decorator | up to 96x96 | Tight crop, transparent. |
| Contact sheet preview | generated | Diagnostic only. |
| Motion sheet | generated | Diagnostic only; checks eye and mouth frame progress independently. |

Adjust sizes only before generation starts. Do not mix dimensions inside one pack.

## Frame Semantics

Eye frames:

```text
0 = open / emotion-resting
1 = half-open or expressive transition
2 = narrow / blink transition
3 = closed or strongest expression
```

Mouth frames:

```text
0 = closed
1 = small open
2 = medium open
3 = wide open
```

The firmware maps `weight` or open ratio to frame index. Do not encode timing in asset filenames.

## Firmware Budget Policy

Default pack output is a component-sprite contract, not a full-screen animation contract.

The default 4-frame eye/mouth count is chosen because it is enough for readable blink and lip motion while keeping generation, QA, and LVGL conversion tractable. It also matches the current `ImageAvatarPack` community direction, where `frameCount` is data-driven and 4-frame eye/mouth strips are used as the demo baseline.

Do not increase frame counts inside a run after generation starts. If a project intentionally wants smoother motion, change the manifest contract and firmware renderer first, then regenerate the whole affected component family. Sensible expansion tiers are:

| Tier | Eyes | Mouth | Use |
| --- | ---: | ---: | --- |
| Default | 4 frames per side | 4 frames | First production pack and normal ImageAvatar use. |
| Smooth mouth | 4 frames per side | 6 frames | Better speech mouth shapes after firmware smoke testing. |
| Smooth blink | 6-7 frames per side | 4-6 frames | Only when blink smoothness matters and firmware mapping is updated. |

Avoid full-screen frame swaps for the official ESP-IDF ImageAvatar path. A single 320x240 RGB565 frame is 153,600 bytes. A 14-image full-screen layered set is about 2.1MB before descriptors, and a 90-image precomposed face/eyes/mouth matrix is far larger. If a runtime chooses full-screen swaps anyway, it should be treated as a separate firmware target with explicit Flash/PSRAM budgeting, not as this skill's default output.

For LVGL handoff, keep source PNGs as editable masters but convert accepted firmware assets to predecoded descriptors where possible:

- RGB565 for fully opaque body/background layers.
- RGB565A8 or another alpha-capable LVGL format for transparent eyes, mouth, hands, and decorators.
- Avoid runtime PNG/GIF decoding for core face parts unless the target firmware has enabled decoders and passed device-side performance tests.

## Manifest Schema

Use paths relative to `manifest.json`.

Anchors are center points, not top-left coordinates. `leftEye` and `rightEye` are the centers of 48x48 eye frames; `mouth` is the center of 96x48 mouth frames. The default values are starting placeholders and must be calibrated to the generated neutral face before finalization.

```json
{
  "id": "my-stackchan",
  "displayName": "My StackChan",
  "canvas": { "width": 320, "height": 240 },
  "frames": {
    "eye": { "width": 48, "height": 48, "count": 4 },
    "mouth": { "width": 96, "height": 48, "count": 4 }
  },
  "anchors": {
    "leftEye": { "x": 92, "y": 88 },
    "rightEye": { "x": 180, "y": 88 },
    "mouth": { "x": 160, "y": 135 }
  },
  "body": "body/base.png",
  "emotions": {
    "neutral": {
      "concept": "concepts/neutral.png",
      "leftEye": ["eyes/neutral/left_0.png", "eyes/neutral/left_1.png", "eyes/neutral/left_2.png", "eyes/neutral/left_3.png"],
      "rightEye": ["eyes/neutral/right_0.png", "eyes/neutral/right_1.png", "eyes/neutral/right_2.png", "eyes/neutral/right_3.png"],
      "mouth": ["mouth/neutral/0.png", "mouth/neutral/1.png", "mouth/neutral/2.png", "mouth/neutral/3.png"]
    }
  },
  "decorators": {
    "heart": "decorators/heart.png",
    "sweat": "decorators/sweat.png",
    "anger": "decorators/anger.png",
    "tear": "decorators/tear.png",
    "dizzy": "decorators/dizzy.png"
  }
}
```

The real manifest must include every required emotion.

## LVGL Handoff

The pack can be converted later into LVGL C image descriptors. Keep source PNGs as the canonical editable assets. Generated LVGL `.c` files belong in firmware, not in the image-pack skill output unless the user asks for firmware integration.

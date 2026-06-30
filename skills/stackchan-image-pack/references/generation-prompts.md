# Generation Prompts

Use these as templates. Keep prompts short, state-specific, sprite-production oriented, and grounded in `identity-notes.md` plus `canonical-style.png`, matching `hatch-pet` prompt discipline.

## Shared Constraints

Append to every generation prompt:

```text
Flat solid chroma-key background only, no scenery, no floor plane, no shadows, no glow, no blur, no text, no labels, no frame numbers, no visible grid, no watermark.
Hatch-pet-like pixel sprite style by default: compact mascot silhouette, simple face, limited palette, crisp outline, flat cel shading, hard opaque pixel-friendly edges, and clean chroma-key extraction.
Make the character appealing and polished: balanced proportions, clear focal face, expressive readable eyes and mouth, harmonious color accents, and a cute StackChan personality.
Preserve the same character identity, silhouette, proportions, palette, material, line quality, and face language from the canonical reference.
Keep the subject centered, fully visible, crisp-edged, and separated from the background.
Do not use the chroma-key color inside the subject.
Facial proportions must be correct in the generated output itself. Do not depend on postprocessing to resize, redraw, crop, recenter, or relocate eyes or mouth.
```

## Neutral Style Candidate

```text
Create one front-facing StackChan ImageAvatar sprite concept on a 320x240 canvas.
Use the attached reference image as identity and style inspiration.
Expression: neutral, calm, friendly, compact, hatch-pet-like, and readable on a small robot screen.
Show the full head/body composition suitable for later separation into body, eyes, and mouth.
Use the attached face-proportion guide only to keep eyes and mouth readable at StackChan screen scale; do not draw the guide.
Default style is pixel-art-adjacent: chunky silhouette, simple dark outline, limited palette, flat cel shading, visible stepped edges.
The result should be attractive enough to become the canonical style: cute, balanced, expressive, and polished, not generic filler art.
No text. No logo copying. No background scene.
```

## Emotion Concept

```text
Create one 320x240 front-facing StackChan avatar concept for emotion: <emotion>.
Use canonical-style.png as the strict identity and hatch-pet-like sprite style reference.
Change only the expression language: eyes, mouth, brows/face attitude, and subtle pose mood.
Keep body shape, palette, material, proportions, line style, and screen composition consistent.
Use the attached face-proportion guide only to keep eyes and mouth at the accepted screen-scale proportions; do not draw the guide.
Keep the expression appealing and readable at device scale.
This is a concept preview, not a sprite strip.
```

## Body Base

```text
Create the base body/head layer for a StackChan ImageAvatar pack on a 320x240 canvas.
Use canonical-style.png as the strict reference.
Render the character body/head and any permanent accessories only.
The eye and mouth areas must be clean and ready for separate eye and mouth sprites; do not draw final pupils, eyelids, mouth, teeth, tongue, or expression marks.
Use the attached face-proportion guide only to reserve clean feature areas at the intended scale; do not draw the guide.
Keep the body centered and aligned for overlay at 320x240.
```

## Eye Strip

```text
Create one horizontal sprite strip for the <left|right> eye of the same StackChan character, emotion: <emotion>.
Each frame is 48x48; total image is 192x48.
Use the attached strip layout guide only for slot count, spacing, centering, and padding; do not draw the guide.
Use the attached body base, matching emotion concept, and face-proportion guide to match the final intended eye scale on the 320x240 face.
upstream generation contract: create the eye at the correct apparent size, shape, and visual weight now.
Frame order: open, half-open or expression transition, narrow/blink transition, closed or strongest expression.
Keep the same scale, anchor point, palette, outline, material, hatch-pet-like pixel style, and baseline across all four frames.
Use generous padding inside each 48x48 slot. No visible slot borders.
Regenerate this component if the eye would need script scaling, redrawing, or manual relocation to fit the face.
Do not rely on postprocessing to fix eye size, eye position, line weight, or expression readability.
```

## Mouth Strip

```text
Create one horizontal sprite strip for the mouth of the same StackChan character, emotion: <emotion>.
Each frame is 96x48; total image is 384x48.
Use the attached strip layout guide only for slot count, spacing, centering, and padding; do not draw the guide.
Use the attached body base, matching emotion concept, and face-proportion guide to match the final intended mouth scale on the 320x240 face.
upstream generation contract: create the mouth at the correct apparent size, shape, and visual weight now.
Frame order: closed, small open, medium open, wide open.
Keep the same anchor point, palette, outline, material, hatch-pet-like pixel style, and baseline across all four frames.
Use mouth shapes suitable for speech animation on a 320x240 robot avatar.
The closed mouth must still be readable at device scale, and open mouth frames must stay visually compatible with the face-proportion guide.
No visible slot borders.
Regenerate this component if the mouth would need script scaling, redrawing, or manual relocation to fit the face.
Do not rely on postprocessing to fix mouth size, mouth position, line weight, or expression readability.
```

## Decorator

```text
Create one compact StackChan avatar decorator: <heart|sweat|anger|tear|dizzy>.
Canvas up to 96x96 with tight crop and generous transparent-ready padding.
Style must match canonical-style.png.
The symbol should be bold, readable, opaque enough for clean extraction, and suitable for overlay near the avatar face.
No detached extra symbols, no background scene, no text.
```

## Repair Prompt

```text
Repair only this StackChan asset: <asset id>.
Problem: <specific QA failure>.
Keep the same character identity and style from canonical-style.png.
Keep the same output dimensions, frame count, frame order, anchor point, and chroma-key background.
Regenerate the smallest failing visual job with $imagegen. Do not fix the artwork by local drawing, scripted scaling, per-frame recentering, or hardcoded mouth/eye reconstruction.
Change only what is necessary in the generated output to fix the QA failure.
```

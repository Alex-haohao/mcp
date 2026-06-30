# QA Rubric

## Blockers

Reject the pack or repair the smallest failing asset when:

- The character identity changes across emotions or frames.
- The pack drifts away from the default hatch-pet-like pixel/sprite style without an explicit user override.
- The selected design is bland, awkward, visually unbalanced, hard to read, or not polished/cute enough for the chosen art direction.
- Body base includes final eyes or mouth that will conflict with overlays.
- Any asset has scenery, text, shadows, glows, frame borders, copied layout-guide marks, or watermark.
- Chroma-key removal deletes part of the character or leaves obvious halos.
- Postprocessing was rerun on already-normalized `decoded/` assets instead of recorded raw `source_path` outputs, causing body shrink, crop drift, or strip drift.
- Eye or mouth frames have inconsistent size, anchor, line style, material, or palette.
- Eye or mouth strip content sits against one side of its frame slot after postprocessing; each frame must be centered in its own slot.
- A strip has the wrong frame count or visible slot borders.
- Any required emotion is missing.
- `qa/postprocess-summary.json`, `qa/finalize-summary.json`, `qa/validation.json`, `qa/contact-sheet.png`, or `qa/previews/*.gif` is missing.
- Manifest references a missing file or wrong dimensions.
- Manifest anchors are still uncalibrated defaults when the generated face is elsewhere on the canvas.
- Contact sheet places eyes or mouth outside the face, on hair, or beside the character.
- Contact sheet does not read clearly at 320x240 preview scale.
- Motion previews show anchor jumps, size popping, unreadable expression changes, or distracting mouth/eye motion.
- Decorators have not been inspected separately; they are not covered by the standard emotion contact sheet.

## Identity Checks

- Same silhouette and proportions.
- Same color palette and material.
- Same eye language and mouth style.
- Same pixel-art-adjacent line quality, edge hardness, and flat shading.
- Same permanent accessories.

## Appeal Checks

- Clear focal face and silhouette at 320x240.
- Balanced head/body proportions for StackChan's screen.
- Harmonious limited palette with one or two accent colors.
- Eyes and mouth are expressive, cute, and readable without visual clutter.
- The design feels intentional and polished rather than generic or merely file-complete.

## Runtime Checks

- `neutral` first frame works as the safe default.
- `happy`, `angry`, `sad`, `doubt`, and `sleepy` are distinguishable at device size.
- `postprocess_stackchan_assets.py` processed the 30 final decoded source assets from `imagegen-jobs.json`.
- Final output contains exactly 48 eye frames and 24 mouth frames for the default 6-emotion, 4-frame contract.
- All frames read as one hatch-pet-like StackChan sprite family: compact silhouette, limited palette, crisp outline, flat cel shading, and no mixed illustration styles.
- Eye frame 0 to 3 progresses coherently.
- Mouth frame 0 to 3 progresses from closed to open.
- Left and right eyes are symmetric unless the design intentionally needs asymmetry.
- Decorators are compact and readable without clutter.
- `final/manifest.template.json` anchors are calibrated as center points for the generated face before finalization.
- Standard validation is treated as structural only; visual QA must catch green residue, off-face overlays, bad strips, and weak decorators.

## Repair Policy

Repair in this order:

1. Single generated component strip.
2. One emotion's eye and mouth set.
3. One decorator.
4. Body base.
5. Canonical style only when broad identity drift affects the whole pack.

Do not regenerate the full pack just because one strip fails.

When a repaired asset is recorded, rerun `postprocess_stackchan_assets.py`, `finalize_stackchan_pack.py`, validation, contact sheet generation, and motion previews from the repaired source. Do not patch final split frames by hand unless the user explicitly asks for a one-off forensic repair.

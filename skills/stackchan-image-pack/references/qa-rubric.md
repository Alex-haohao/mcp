# QA Rubric

## Blockers

Reject the pack or repair the smallest failing asset when:

- The character identity changes across emotions or frames.
- The pack drifts away from the default hatch-pet-like pixel/sprite style without an explicit user override.
- The selected design is bland, awkward, visually unbalanced, hard to read, or not polished/cute enough for the chosen art direction.
- Body base includes final eyes or mouth that will conflict with overlays.
- Any asset has scenery, text, shadows, glows, frame borders, copied layout-guide marks, or watermark.
- Chroma-key removal deletes part of the character or leaves obvious halos.
- Postprocessing was rerun on already-normalized `decoded/` assets instead of recorded raw `source_path` outputs, hiding body shrink, crop drift, or strip drift.
- Postprocessing crops content, scales individual eyes/mouths, redraws features, or recenters frames to make a bad generated component pass.
- Eye or mouth frames have inconsistent size, anchor, line style, material, or palette.
- Eye or mouth strip content sits against one side of its frame slot in the generated source. Regenerate the component upstream; do not recenter it locally.
- A strip has the wrong frame count or visible slot borders.
- Any required emotion is missing.
- `qa/postprocess-summary.json`, `qa/finalize-summary.json`, `qa/validation.json`, `qa/contact-sheet.png`, `qa/motion-sheet.png`, or `qa/previews/*.gif` is missing.
- Manifest references a missing file or wrong dimensions.
- Manifest anchors are still uncalibrated defaults when the generated face is elsewhere on the canvas.
- For production firmware handoff or visually questioned packs, `qa/semantic-fit/semantic-fit-report.json`, `qa/semantic-fit/neutral-semantic-overlay.png`, `qa/anchor-fit/anchor-fit-report.json`, or `qa/anchor-fit/*-concept-vs-overlay.png` is missing.
- Semantic-fit reports any eye or mouth center outside tolerance, any feature outside its face slot, unreadable content size, or neutral-eye symmetry failure.
- Anchor-fit comparison shows that the generated concept face is materially better aligned, better proportioned, or more expressive than the body plus anchored first-frame overlays.
- Contact sheet places eyes or mouth outside the face, on hair, or beside the character.
- Contact sheet does not read clearly at 320x240 preview scale.
- Motion sheet or previews show anchor jumps, size popping, unreadable expression changes, distracting mouth/eye motion, or missing difference frames.
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
- `postprocess_stackchan_assets.py` writes `mode: "upstream-preserving"` and does not crop, scale, redraw, or recenter facial feature content.
- Eye and mouth strips were generated with canonical style, body base, matching emotion concept, strip guide, and face-proportion guide attached.
- `references/face-layout.json` matches the accepted face when semantic-fit is used before firmware conversion.
- `qa/anchor-fit/anchor-fit-report.json` has been reviewed for frame content centering, tiny mouth warnings, and canvas-center offsets.
- `qa/motion-sheet.png` has been reviewed as two independent channels: eye frame progression with mouth frame 0, and mouth frame progression with eye frame 0.
- Standard validation is treated as structural only; visual QA must catch green residue, off-face overlays, bad strips, and weak decorators.
- Anchor-fit diagnostics are treated as visual evidence, not automatic acceptance; a generated report with warnings can still be acceptable only after inspection, and a warning-free report can still fail if the composed face looks wrong.

## Repair Policy

Repair means regenerating the smallest failing `$imagegen` visual job or calibrating manifest anchors. It does not mean local drawing, hardcoded reconstruction, scripted feature scaling, or per-frame recentering.

Repair in this order:

1. Single generated component strip.
2. One emotion's eye and mouth set.
3. One decorator.
4. Body base.
5. Canonical style only when broad identity drift affects the whole pack.

Do not regenerate the full pack just because one strip fails.

When a replacement asset is recorded, rerun `postprocess_stackchan_assets.py`, `finalize_stackchan_pack.py`, validation, semantic-fit when applicable, contact sheet generation, anchor-fit when applicable, motion sheet, and motion previews from the replacement source. Do not patch final split frames by hand unless the user explicitly asks for a one-off forensic repair.

When the symptom is "body proportion is correct but eyes or mouth look wrong", do not start by changing firmware coordinates or running a local repair script. First run/inspect semantic-fit, anchor-fit, contact sheet, and motion sheet, then classify the root cause:

- accepted concept face is wrong;
- body base does not match the accepted concept;
- generated eye or mouth strip is too small, too large, off-slot, or stylistically weak;
- manifest anchors are uncalibrated;
- runtime coordinate/scale behavior only if source-level overlays look correct but the device does not.

Fix the first failing source layer by regenerating the relevant `$imagegen` job or by calibrating the manifest, then rerun the deterministic QA chain.

Do not sync LVGL descriptors or firmware placement constants until source-level semantic-fit and anchor-fit pass. Firmware constants must be derived from the accepted manifest; hand-tuning them before source QA hides the real failure.

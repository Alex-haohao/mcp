# Worker Prompts

Use lightweight workers for image-heavy jobs when available. The parent agent owns run preparation, manifest updates, deterministic scripts, repair decisions, and handoff.

## Visual Job Worker

```text
Generate one StackChan image-pack visual job.

Run dir: <absolute run dir>
Job id: <job-id>
Prompt file: <absolute prompt file>
Retry prompt file: <absolute retry prompt file, or none>
Context files:
- <absolute run dir>/references/identity-notes.md
- <absolute run dir>/references/art-direction.md
Input images:
- <absolute path> - <role>

Use $imagegen only. Read the prompt and context files, then attach every listed input image. If $imagegen returns a transport-level Bad Request, retry once with the retry prompt and the same input images.

Before returning, visually check: exact requested canvas or strip size, correct frame count, same canonical identity, hatch-pet-like pixel/sprite style, flat chroma background or alpha, no copied layout-guide marks, no text, no scenery, no shadows/glows, no clipping, no mixed style, and strong appeal at 320x240.

Do not edit manifests, copy files into decoded, promote canonical style, run deterministic scripts, repair other jobs, or inspect unrelated files. Do not include Markdown image previews, base64, or extra attachments in the final response.

Return exactly:
selected_source=/absolute/path/to/selected-output.png
qa_note=<one sentence>
```

## Final Visual QA Worker

```text
Visually QA one finalized StackChan image pack.

Run dir: <absolute run dir>
Contact sheet: <absolute run dir>/qa/contact-sheet.png
Preview dir: <absolute run dir>/qa/previews
Validation JSON: <absolute run dir>/qa/validation.json
Postprocess summary: <absolute run dir>/qa/postprocess-summary.json
Finalize summary: <absolute run dir>/qa/finalize-summary.json
Identity notes: <absolute run dir>/references/identity-notes.md
Art direction: <absolute run dir>/references/art-direction.md

Inspect the contact sheet, all preview GIFs, component strips, and decorators. Confirm all six emotions are the same StackChan character, preserve hatch-pet-like pixel/sprite style, have appealing proportions, clear silhouette, harmonious palette, expressive readable eyes and mouth, stable anchors, no size popping, no copied guide marks, no chroma residue or halos, no off-face overlays, no weak decorators, and no mixed rendering styles.

Fail the pack if it is complete but visually bland, inconsistent, hard to read at device size, off-style, or not cute/polished enough for the chosen art direction.

Do not edit files, queue repairs, package, clean up, or inspect unrelated files.

Return exactly:
visual_qa=pass|fail
qa_note=<one sentence summary>
repair_assets=<comma-separated asset ids, or none>
repair_notes=<short asset-specific notes, or none>
```

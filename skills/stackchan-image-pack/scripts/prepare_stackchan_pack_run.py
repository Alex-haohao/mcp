#!/usr/bin/env python3
"""Prepare a StackChan ImageAvatar image-pack generation run."""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except Exception:  # pragma: no cover - handled at runtime
    Image = None
    ImageDraw = None


EMOTIONS = ["neutral", "happy", "angry", "sad", "doubt", "sleepy"]
DECORATORS = ["heart", "sweat", "anger", "tear", "dizzy"]
EYE_FRAME = {"width": 48, "height": 48, "count": 4}
MOUTH_FRAME = {"width": 96, "height": 48, "count": 4}
CANVAS = {"width": 320, "height": 240}
DEFAULT_ANCHORS = {
    "leftEye": {"x": 92, "y": 88},
    "rightEye": {"x": 180, "y": 88},
    "mouth": {"x": 160, "y": 135},
}
DEFAULT_FACE_PROPORTION_CONTRACT = {
    "purpose": "upstream generation guide for readable StackChan ImageAvatar face proportions",
    "canvas": CANVAS,
    "faceBox": {"x": 96, "y": 42, "width": 128, "height": 102},
    "leftEyeSlot": {"x": 112, "y": 64, "width": 48, "height": 40},
    "rightEyeSlot": {"x": 160, "y": 64, "width": 48, "height": 40},
    "mouthSlot": {"x": 126, "y": 102, "width": 68, "height": 30},
    "rules": [
        "Generate features at their final intended apparent size; do not expect scripts to resize, redraw, or relocate them.",
        "Eyes should be large and readable at 320x240 while leaving clear padding inside each 48x48 frame.",
        "The closed mouth must remain readable at 320x240, and open mouth frames must stay inside the mouth slot.",
        "If a generated component misses this proportion contract, regenerate that component upstream.",
    ],
}
STACKCHAN_SAFE_STYLE = (
    "StackChan-safe sprite: compact front-facing robot mascot, readable on a "
    "320x240 device display, simple face language, stable palette/materials, "
    "clear silhouette, crisp opaque edges, polished appeal, and clean chroma-key extraction."
)
STYLE_PRESETS = {
    "pixel": (
        "Pixel-art-adjacent hatch-pet style with a chunky compact silhouette, "
        "simple dark outline, limited palette, flat cel shading, visible stepped "
        "edges, and no painterly or photoreal texture."
    ),
    "auto": (
        "Infer a pet-safe style from the reference, but keep it close to the "
        "hatch-pet sprite workflow: compact, hard-edged, readable, and easy to extract."
    ),
    "sticker": "Polished sticker mascot with bold clean shapes, crisp outline, and flat colors.",
    "flat-vector": "Flat vector mascot with simple geometric forms and minimal shading.",
    "3d-toy": "Stylized toy mascot with rounded forms and simple non-photoreal materials.",
}
CHROMA_KEY_CANDIDATES = [
    ("magenta", "#FF00FF"),
    ("cyan", "#00FFFF"),
    ("yellow", "#FFFF00"),
    ("blue", "#0000FF"),
    ("orange", "#FF7F00"),
    ("green", "#00FF00"),
]


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-") or "stackchan-pack"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_layout_guide(path: Path, width: int, height: int, cols: int, rows: int, _label: str) -> None:
    if Image is None or ImageDraw is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (width, height), "#f7f7f7")
    draw = ImageDraw.Draw(image)
    cell_w = width / cols
    cell_h = height / rows
    for col in range(cols + 1):
        x = round(col * cell_w)
        draw.line((x, 0, x, height), fill="#bbbbbb")
    for row in range(rows + 1):
        y = round(row * cell_h)
        draw.line((0, y, width, y), fill="#bbbbbb")
    margin = 6
    draw.rectangle((margin, margin, width - margin - 1, height - margin - 1), outline="#777777")
    image.save(path)


def make_face_proportion_guide(path: Path) -> None:
    if Image is None or ImageDraw is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (CANVAS["width"], CANVAS["height"]), "#f7f7f7")
    draw = ImageDraw.Draw(image)
    contract = DEFAULT_FACE_PROPORTION_CONTRACT

    def rect(key: str, color: str, width: int) -> None:
        value = contract[key]
        draw.rectangle(
            (
                int(value["x"]),
                int(value["y"]),
                int(value["x"] + value["width"]),
                int(value["y"] + value["height"]),
            ),
            outline=color,
            width=width,
        )

    rect("faceBox", "#38a169", 2)
    rect("leftEyeSlot", "#3182ce", 2)
    rect("rightEyeSlot", "#3182ce", 2)
    rect("mouthSlot", "#d53f8c", 2)
    draw.line((160, 18, 160, 222), fill="#b8b8b8", width=1)
    image.save(path)


def parse_hex_color(value: str) -> tuple[int, int, int]:
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise SystemExit(f"invalid chroma key color: {value}; expected #RRGGBB")
    return tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"


def color_distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> float:
    return math.sqrt(sum((left[index] - right[index]) ** 2 for index in range(3)))


def sampled_reference_pixels(paths: list[Path]) -> list[tuple[int, int, int]]:
    if Image is None:
        return []
    pixels: list[tuple[int, int, int]] = []
    for path in paths:
        with Image.open(path) as opened:
            image = opened.convert("RGBA")
            image.thumbnail((128, 128), Image.Resampling.LANCZOS)
            data = image.tobytes()
            for index in range(0, len(data), 4):
                red, green, blue, alpha = data[index : index + 4]
                if alpha > 16:
                    pixels.append((red, green, blue))
    non_background = [
        pixel
        for pixel in pixels
        if not (pixel[0] > 244 and pixel[1] > 244 and pixel[2] > 244)
    ]
    return non_background or pixels


def choose_chroma_key(reference_paths: list[Path], requested: str) -> dict[str, object]:
    if requested.lower() != "auto":
        rgb = parse_hex_color(requested)
        return {"hex": rgb_to_hex(rgb), "rgb": list(rgb), "name": "user-selected", "selection": "manual"}

    pixels = sampled_reference_pixels(reference_paths)
    if not pixels:
        rgb = parse_hex_color("#FF00FF")
        return {"hex": "#FF00FF", "rgb": list(rgb), "name": "magenta", "selection": "fallback"}

    scored: list[tuple[float, int, str, tuple[int, int, int]]] = []
    for preference_index, (name, hex_color) in enumerate(CHROMA_KEY_CANDIDATES):
        rgb = parse_hex_color(hex_color)
        distances = sorted(color_distance(rgb, pixel) for pixel in pixels)
        percentile_index = max(0, min(len(distances) - 1, int(len(distances) * 0.01)))
        scored.append((distances[percentile_index], -preference_index, name, rgb))
    score, _preference, name, rgb = max(scored)
    return {"hex": rgb_to_hex(rgb), "rgb": list(rgb), "name": name, "selection": "auto", "score": round(score, 2)}


def resolved_style_contract(style_preset: str, raw_style_notes: str) -> str:
    style_preset = style_preset.strip().lower()
    if style_preset not in STYLE_PRESETS:
        allowed = ", ".join(sorted(STYLE_PRESETS))
        raise SystemExit(f"invalid style preset: {style_preset}; expected one of: {allowed}")
    preset_contract = STYLE_PRESETS[style_preset]
    if not raw_style_notes.strip():
        return f"{STACKCHAN_SAFE_STYLE} Style `{style_preset}`: {preset_contract}"
    return f"{STACKCHAN_SAFE_STYLE} Style `{style_preset}`: {preset_contract} User style notes: {raw_style_notes.strip()}."


def shared_constraints(args: argparse.Namespace) -> str:
    chroma_key = args.chroma_key["hex"]
    chroma_name = args.chroma_key["name"]
    return f"""
Style: {args.style_contract}
Flat solid pure {chroma_name} {chroma_key} chroma-key background only.
Use hatch-pet-like sprite discipline: compact mascot shape, crisp opaque pixel-friendly edges, stable scale, safe padding, and no soft painterly detail.
Make the character appealing and polished: balanced proportions, clear focal face, expressive readable eyes and mouth, harmonious color accents, and a cute StackChan personality.
No scenery, floor plane, shadows, glows, blur, text, labels, frame numbers, visible grid, watermark, or guide marks.
Preserve the same character identity, silhouette, proportions, palette, material, line quality, and face language from the canonical reference.
Keep the subject centered, fully visible, crisp-edged, and separated from the background.
Do not use {chroma_key} or close chroma-key colors inside the subject.
"""


def prompt_style_candidate(args: argparse.Namespace, index: int) -> str:
    return f"""
Create neutral StackChan ImageAvatar sprite style candidate {index} on a 320x240 canvas.
Primary description: {args.description}
Style preset: {args.style_preset}
Style contract: {args.style_contract}
Use attached reference images as identity and style inspiration.
Expression: neutral, calm, friendly, compact, hatch-pet-like, and readable on a small robot screen.
Show the full head/body composition suitable for later separation into body, eyes, and mouth.
Use the attached face-proportion guide only to keep the eyes and mouth at readable StackChan screen proportions; do not draw the guide.
Make it pixel-art-adjacent by default: chunky silhouette, simple face, limited palette, crisp outline, flat cel shading, and visible stepped edges.
The result should be attractive enough to become the canonical style: cute, balanced, expressive, and polished, not generic filler art.
No logo copying.
{shared_constraints(args)}
"""


def prompt_emotion(args: argparse.Namespace, emotion: str) -> str:
    return f"""
Create one 320x240 front-facing StackChan avatar concept for emotion: {emotion}.
Use canonical-style.png as the strict identity and hatch-pet-like pixel/sprite style reference.
Change only the expression language: eyes, mouth, brows or face attitude, and subtle pose mood.
Keep body shape, palette, material, proportions, line style, and screen composition consistent.
Use the attached face-proportion guide only to preserve readable eye and mouth scale on the 320x240 face; do not draw the guide.
Keep the expression appealing and readable at device scale.
This is a concept preview, not a sprite strip.
{shared_constraints(args)}
"""


def prompt_body(args: argparse.Namespace) -> str:
    return f"""
Create the base body/head layer for a StackChan ImageAvatar pack on a 320x240 canvas.
Use canonical-style.png as the strict reference.
Render the character body/head and permanent accessories only.
The eye and mouth areas must be clean and ready for separate eye and mouth sprites.
Do not draw final pupils, eyelids, mouth, teeth, tongue, or expression marks.
Use the attached face-proportion guide only to reserve clean feature areas at the intended scale; do not draw the guide.
Keep the body centered and aligned for overlay at 320x240.
{shared_constraints(args)}
"""


def prompt_eye(args: argparse.Namespace, emotion: str, side: str) -> str:
    return f"""
Create one horizontal sprite strip for the {side} eye of the same StackChan character, emotion: {emotion}.
Each frame is 48x48; total image is 192x48.
Use the attached strip layout guide only for slot count, spacing, centering, and padding; do not draw the guide.
Use the attached body base, {emotion} concept, and face-proportion guide to match the final intended eye scale on the 320x240 face.
upstream generation contract: create the eye at the correct apparent size, shape, and visual weight now.
Frame order: open, half-open or expression transition, narrow/blink transition, closed or strongest expression.
Keep the same scale, anchor point, palette, outline, material, pixel-art-adjacent style, and baseline across all four frames.
Use generous padding inside each 48x48 slot. No visible slot borders.
Regenerate this component if the eye would need script scaling, redrawing, or manual relocation to fit the face.
Do not rely on postprocessing to fix eye size, eye position, line weight, or expression readability.
{shared_constraints(args)}
"""


def prompt_mouth(args: argparse.Namespace, emotion: str) -> str:
    return f"""
Create one horizontal sprite strip for the mouth of the same StackChan character, emotion: {emotion}.
Each frame is 96x48; total image is 384x48.
Use the attached strip layout guide only for slot count, spacing, centering, and padding; do not draw the guide.
Use the attached body base, {emotion} concept, and face-proportion guide to match the final intended mouth scale on the 320x240 face.
upstream generation contract: create the mouth at the correct apparent size, shape, and visual weight now.
Frame order: closed, small open, medium open, wide open.
Keep the same anchor point, palette, outline, material, pixel-art-adjacent style, and baseline across all four frames.
Use mouth shapes suitable for speech animation on a 320x240 robot avatar.
The closed mouth must still be readable at device scale, and open mouth frames must stay visually compatible with the face-proportion guide.
No visible slot borders.
Regenerate this component if the mouth would need script scaling, redrawing, or manual relocation to fit the face.
Do not rely on postprocessing to fix mouth size, mouth position, line weight, or expression readability.
{shared_constraints(args)}
"""


def prompt_decorator(args: argparse.Namespace, decorator: str) -> str:
    return f"""
Create one compact StackChan avatar decorator: {decorator}.
Canvas up to 96x96 with tight crop and generous transparent-ready padding.
Style must match canonical-style.png.
The symbol should be bold, readable, opaque enough for clean extraction, and suitable for overlay near the avatar face.
No detached extra symbols.
{shared_constraints(args)}
"""


def retry_prompt(args: argparse.Namespace, asset_id: str, expected_output: str) -> str:
    return f"""
Retry StackChan ImageAvatar visual job `{asset_id}`.
Expected output: {expected_output}.
Use the attached canonical style and layout guide inputs exactly as construction references.
Preserve the same hatch-pet-like pixel/sprite identity, compact silhouette, limited palette, crisp outline, flat cel shading, and hard opaque extraction edges.
Fix only the previous failure: wrong dimensions, missing frame slot, guide marks, identity drift, style drift, weak readability, bad chroma background, or clipping.
No scenery, text, shadows, glows, blur, speed lines, detached effects, frame numbers, visible borders, or guide marks.
{shared_constraints(args)}
"""


def add_job(
    jobs: list[dict],
    job_id: str,
    kind: str,
    prompt_file: str,
    output_path: str,
    input_images: list[dict],
    depends_on: list[str] | None = None,
    retry_prompt_file: str | None = None,
) -> None:
    jobs.append(
        {
            "id": job_id,
            "kind": kind,
            "status": "pending",
            "depends_on": depends_on or [],
            "prompt_file": prompt_file,
            "retry_prompt_file": retry_prompt_file or "",
            "input_images": input_images,
            "output_path": output_path,
            "generation_skill": "$imagegen",
            "requires_grounded_generation": bool(input_images),
            "allow_prompt_only_generation": not bool(input_images),
        }
    )


def build_manifest_template(pack_id: str, display_name: str) -> dict:
    emotions = {}
    for emotion in EMOTIONS:
        emotions[emotion] = {
            "concept": f"concepts/{emotion}.png",
            "leftEye": [f"eyes/{emotion}/left_{i}.png" for i in range(EYE_FRAME["count"])],
            "rightEye": [f"eyes/{emotion}/right_{i}.png" for i in range(EYE_FRAME["count"])],
            "mouth": [f"mouth/{emotion}/{i}.png" for i in range(MOUTH_FRAME["count"])],
        }
    return {
        "id": pack_id,
        "displayName": display_name,
        "canvas": CANVAS,
        "frames": {"eye": EYE_FRAME, "mouth": MOUTH_FRAME},
        "anchors": DEFAULT_ANCHORS,
        "body": "body/base.png",
        "emotions": emotions,
        "decorators": {name: f"decorators/{name}.png" for name in DECORATORS},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack-name", default="Custom StackChan")
    parser.add_argument("--description", default="A custom StackChan avatar image pack")
    parser.add_argument("--reference", action="append", default=[])
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--style-preset", default="pixel", choices=sorted(STYLE_PRESETS))
    parser.add_argument("--style-notes", default="")
    parser.add_argument("--chroma-key", default="auto")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = Path(args.output_dir).expanduser().resolve()
    if run_dir.exists() and args.force:
        shutil.rmtree(run_dir)
    if run_dir.exists() and any(run_dir.iterdir()):
        raise SystemExit(f"output dir already exists and is not empty: {run_dir}")

    pack_id = slugify(args.pack_name)
    raw_reference_paths = [Path(path).expanduser().resolve() for path in args.reference]
    for source in raw_reference_paths:
        if not source.is_file():
            raise SystemExit(f"reference not found: {source}")

    for rel in [
        "references/input",
        "references/layout-guides",
        "prompts/style-candidates",
        "prompts/concepts",
        "prompts/parts",
        "prompts/decorators",
        "prompts/retries",
        "decoded/concepts",
        "decoded/parts",
        "decoded/decorators",
        "final/body",
        "final/concepts",
        "final/decorators",
        "qa",
    ]:
        (run_dir / rel).mkdir(parents=True, exist_ok=True)
    for emotion in EMOTIONS:
        (run_dir / f"final/eyes/{emotion}").mkdir(parents=True, exist_ok=True)
        (run_dir / f"final/mouth/{emotion}").mkdir(parents=True, exist_ok=True)

    make_layout_guide(run_dir / "references/layout-guides/concept-320x240.png", 320, 240, 1, 1, "320x240 concept")
    make_layout_guide(run_dir / "references/layout-guides/eye-strip-4x48.png", 192, 48, 4, 1, "4 x 48x48 eye frames")
    make_layout_guide(run_dir / "references/layout-guides/mouth-strip-4x96.png", 384, 48, 4, 1, "4 x 96x48 mouth frames")
    make_layout_guide(run_dir / "references/layout-guides/decorator-96.png", 96, 96, 1, 1, "96x96 decorator")
    make_face_proportion_guide(run_dir / "references/layout-guides/face-proportion-320x240.png")

    refs: list[dict[str, str]] = []
    copied_reference_paths: list[Path] = []
    for index, source in enumerate(raw_reference_paths, start=1):
        suffix = source.suffix.lower() or ".png"
        copied = run_dir / f"references/input/reference-{index:02d}{suffix}"
        shutil.copy2(source, copied)
        refs.append({"path": str(copied.relative_to(run_dir)), "role": "user reference image"})
        copied_reference_paths.append(copied)

    args.style_preset = args.style_preset.strip().lower()
    args.style_contract = resolved_style_contract(args.style_preset, args.style_notes)
    args.chroma_key = choose_chroma_key(copied_reference_paths, args.chroma_key)

    concept_layout = {
        "path": "references/layout-guides/concept-320x240.png",
        "role": "layout guide for 320x240 canvas; use for spacing only, do not copy guide lines",
    }
    face_proportion_layout = {
        "path": "references/layout-guides/face-proportion-320x240.png",
        "role": "face-proportion guide for 320x240 eye and mouth scale; use for proportions only, do not copy guide lines",
    }
    eye_layout = {
        "path": "references/layout-guides/eye-strip-4x48.png",
        "role": "layout guide for four 48x48 eye slots; use for spacing only, do not copy guide lines",
    }
    mouth_layout = {
        "path": "references/layout-guides/mouth-strip-4x96.png",
        "role": "layout guide for four 96x48 mouth slots; use for spacing only, do not copy guide lines",
    }
    decorator_layout = {
        "path": "references/layout-guides/decorator-96.png",
        "role": "layout guide for 96x96 decorator canvas; use for spacing only, do not copy guide lines",
    }
    canonical = [{"path": "references/canonical-style.png", "role": "canonical hatch-pet-style identity reference"}] + refs

    jobs: list[dict] = []
    for index in range(1, 4):
        prompt_rel = f"prompts/style-candidates/neutral-style-{index}.md"
        write_text(run_dir / prompt_rel, prompt_style_candidate(args, index))
        retry_rel = f"prompts/retries/neutral-style-{index}.md"
        output_rel = f"decoded/concepts/neutral-style-{index}.png"
        write_text(run_dir / retry_rel, retry_prompt(args, f"neutral-style-{index}", "one 320x240 neutral style candidate"))
        add_job(
            jobs,
            f"neutral-style-{index}",
            "style-candidate",
            prompt_rel,
            output_rel,
            [*refs, concept_layout, face_proportion_layout],
            retry_prompt_file=retry_rel,
        )

    jobs.append(
        {
            "id": "canonical-style",
            "kind": "manual-selection",
            "status": "pending",
            "depends_on": ["neutral-style-1", "neutral-style-2", "neutral-style-3"],
            "prompt_file": "",
            "retry_prompt_file": "",
            "input_images": [{"path": f"decoded/concepts/neutral-style-{index}.png", "role": f"style candidate {index}"} for index in range(1, 4)],
            "output_path": "references/canonical-style.png",
            "generation_skill": "manual",
            "requires_grounded_generation": False,
            "allow_prompt_only_generation": False,
            "selection_policy": "choose the most appealing hatch-pet-like pixel/sprite candidate with strongest identity consistency and device readability",
        }
    )

    for emotion in EMOTIONS:
        prompt_rel = f"prompts/concepts/{emotion}.md"
        write_text(run_dir / prompt_rel, prompt_emotion(args, emotion))
        retry_rel = f"prompts/retries/concept-{emotion}.md"
        output_rel = f"decoded/concepts/{emotion}.png"
        write_text(run_dir / retry_rel, retry_prompt(args, f"concept-{emotion}", "one 320x240 emotion concept"))
        add_job(
            jobs,
            f"concept-{emotion}",
            "emotion-concept",
            prompt_rel,
            output_rel,
            [*canonical, concept_layout, face_proportion_layout],
            ["canonical-style"],
            retry_rel,
        )

    prompt_rel = "prompts/parts/body-base.md"
    write_text(run_dir / prompt_rel, prompt_body(args))
    retry_rel = "prompts/retries/body-base.md"
    write_text(run_dir / retry_rel, retry_prompt(args, "body-base", "one 320x240 body/head base layer"))
    add_job(
        jobs,
        "body-base",
        "body",
        prompt_rel,
        "decoded/parts/body-base.png",
        [*canonical, concept_layout, face_proportion_layout],
        ["canonical-style"],
        retry_rel,
    )

    for emotion in EMOTIONS:
        emotion_context = [
            {
                "path": "decoded/parts/body-base.png",
                "role": "accepted body base for final 320x240 overlay context",
            },
            {
                "path": f"decoded/concepts/{emotion}.png",
                "role": f"accepted {emotion} concept showing final face proportion and expression",
            },
        ]
        part_depends_on = ["canonical-style", "body-base", f"concept-{emotion}"]
        for side in ["left", "right"]:
            prompt_rel = f"prompts/parts/eyes-{emotion}-{side}.md"
            write_text(run_dir / prompt_rel, prompt_eye(args, emotion, side))
            retry_rel = f"prompts/retries/eyes-{emotion}-{side}.md"
            output_rel = f"decoded/parts/eyes-{emotion}-{side}.png"
            write_text(run_dir / retry_rel, retry_prompt(args, f"eyes-{emotion}-{side}", "one 192x48 four-frame eye strip"))
            add_job(
                jobs,
                f"eyes-{emotion}-{side}",
                "eye-strip",
                prompt_rel,
                output_rel,
                [*canonical, *emotion_context, eye_layout, face_proportion_layout],
                part_depends_on,
                retry_rel,
            )
        prompt_rel = f"prompts/parts/mouth-{emotion}.md"
        write_text(run_dir / prompt_rel, prompt_mouth(args, emotion))
        retry_rel = f"prompts/retries/mouth-{emotion}.md"
        output_rel = f"decoded/parts/mouth-{emotion}.png"
        write_text(run_dir / retry_rel, retry_prompt(args, f"mouth-{emotion}", "one 384x48 four-frame mouth strip"))
        add_job(
            jobs,
            f"mouth-{emotion}",
            "mouth-strip",
            prompt_rel,
            output_rel,
            [*canonical, *emotion_context, mouth_layout, face_proportion_layout],
            part_depends_on,
            retry_rel,
        )

    for decorator in DECORATORS:
        prompt_rel = f"prompts/decorators/{decorator}.md"
        write_text(run_dir / prompt_rel, prompt_decorator(args, decorator))
        retry_rel = f"prompts/retries/decorator-{decorator}.md"
        output_rel = f"decoded/decorators/{decorator}.png"
        write_text(run_dir / retry_rel, retry_prompt(args, f"decorator-{decorator}", "one compact transparent decorator up to 96x96"))
        add_job(jobs, f"decorator-{decorator}", "decorator", prompt_rel, output_rel, [*canonical, decorator_layout], ["canonical-style"], retry_rel)

    write_json(
        run_dir / "pack_request.json",
        {
            "pack_id": pack_id,
            "display_name": args.pack_name,
            "description": args.description,
            "style_preset": args.style_preset,
            "style_notes": args.style_notes,
            "style_contract": args.style_contract,
            "chroma_key": args.chroma_key,
            "references": refs,
            "primary_generation_skill": "$imagegen",
            "hatch_pet_alignment": {
                "upstream": "openai/skills hatch-pet",
                "workflow": "canonical identity, upstream face-proportion contract, layout-guide-grounded strips, concise sprite-production prompts, deterministic finalization, contact-sheet QA",
                "visual_default": "pixel-art-adjacent hatch-pet sprite style",
            },
            "face_proportion_contract": DEFAULT_FACE_PROPORTION_CONTRACT,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    write_json(run_dir / "references/face-proportion-contract.json", DEFAULT_FACE_PROPORTION_CONTRACT)
    write_json(
        run_dir / "imagegen-jobs.json",
        {
            "schema_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "run_dir": str(run_dir),
            "primary_generation_skill": "$imagegen",
            "jobs": jobs,
        },
    )
    write_json(run_dir / "final/manifest.template.json", build_manifest_template(pack_id, args.pack_name))
    write_text(
        run_dir / "references/identity-notes.md",
        """
# Identity Notes

Fill this after choosing `references/canonical-style.png`.

- Stable silhouette:
- Palette:
- Line quality:
- Material/finish:
- Eye language:
- Mouth language:
- Permanent accessories:
- Appeal / cuteness hook:
- Best candidate rationale:
- Forbidden drift:
""",
    )
    write_text(
        run_dir / "references/art-direction.md",
        """
# Art Direction

Fill this after choosing `references/canonical-style.png`.

- Chosen candidate:
- Why it looks good:
- Pixel/sprite qualities to preserve:
- Color harmony:
- Readability at 320x240:
- Expression principles:
- Repair priorities:
""",
    )

    print(f"run_dir={run_dir}")
    print(f"jobs={len(jobs)}")
    print(f"manifest_template={run_dir / 'final/manifest.template.json'}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Create anchor-fit diagnostics for a finalized StackChan ImageAvatar pack."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


REQUIRED_EMOTIONS = ["neutral", "happy", "angry", "sad", "doubt", "sleepy"]


def load_rgba(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")


def alpha_bbox_info(path: Path, base_dir: Path) -> dict[str, Any]:
    image = load_rgba(path)
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    info: dict[str, Any] = {
        "path": str(path.relative_to(base_dir)),
        "size": list(image.size),
        "bbox": list(bbox) if bbox else None,
    }
    if bbox:
        x1, y1, x2, y2 = bbox
        content_center = [(x1 + x2) / 2, (y1 + y2) / 2]
        frame_center = [image.width / 2, image.height / 2]
        info.update(
            {
                "content_size": [x2 - x1, y2 - y1],
                "content_center": content_center,
                "frame_center": frame_center,
                "center_delta": [content_center[0] - frame_center[0], content_center[1] - frame_center[1]],
                "alpha_pixels": sum(1 for value in alpha.getdata() if value > 0),
            }
        )
    return info


def paste_center(canvas: Image.Image, image: Image.Image, center: tuple[float, float]) -> tuple[int, int, int, int]:
    x = round(center[0] - image.width / 2)
    y = round(center[1] - image.height / 2)
    canvas.alpha_composite(image, (x, y))
    return (x, y, x + image.width, y + image.height)


def draw_box(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], label: str, color: tuple[int, int, int, int]) -> None:
    draw.rectangle(box, outline=color, width=1)
    cx = (box[0] + box[2]) // 2
    cy = (box[1] + box[3]) // 2
    draw.line((cx - 6, cy, cx + 6, cy), fill=color, width=1)
    draw.line((cx, cy - 6, cx, cy + 6), fill=color, width=1)
    draw.text((cx + 4, cy + 4), label, fill=color)


def make_overlay(
    manifest: dict[str, Any],
    base_dir: Path,
    output: Path,
    emotion: str,
    *,
    wrong_top_left: bool = False,
) -> list[dict[str, Any]]:
    canvas = manifest["canvas"]
    canvas_center = (int(canvas["width"]) / 2, int(canvas["height"]) / 2)
    body = load_rgba(base_dir / manifest["body"])
    entry = manifest["emotions"][emotion]
    pieces = [
        ("leftEye", load_rgba(base_dir / entry["leftEye"][0]), manifest["anchors"]["leftEye"], (255, 0, 0, 255)),
        ("rightEye", load_rgba(base_dir / entry["rightEye"][0]), manifest["anchors"]["rightEye"], (0, 160, 255, 255)),
        ("mouth", load_rgba(base_dir / entry["mouth"][0]), manifest["anchors"]["mouth"], (255, 0, 180, 255)),
    ]

    boxes: list[dict[str, Any]] = []
    draw = ImageDraw.Draw(body)
    for name, image, anchor, color in pieces:
        if wrong_top_left:
            center_offset = (int(anchor["x"]) - canvas_center[0], int(anchor["y"]) - canvas_center[1])
            top_left = (round(center_offset[0]), round(center_offset[1]))
            body.alpha_composite(image, top_left)
            box = (top_left[0], top_left[1], top_left[0] + image.width, top_left[1] + image.height)
        else:
            box = paste_center(body, image, (float(anchor["x"]), float(anchor["y"])))
        draw_box(draw, box, name, color)
        boxes.append({"part": name, "box": list(box)})

    output.parent.mkdir(parents=True, exist_ok=True)
    body.convert("RGB").save(output)
    return boxes


def make_concept_comparison(manifest: dict[str, Any], base_dir: Path, overlay_path: Path, output: Path, emotion: str) -> None:
    concept_rel = manifest["emotions"][emotion].get("concept")
    if not concept_rel:
        return
    concept = load_rgba(base_dir / concept_rel)
    overlay = load_rgba(overlay_path)
    width = concept.width + overlay.width
    height = max(concept.height, overlay.height)
    image = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    image.alpha_composite(concept, (0, 0))
    image.alpha_composite(overlay, (concept.width, 0))
    draw = ImageDraw.Draw(image)
    draw.text((4, 4), f"{emotion} concept", fill=(0, 0, 0, 255))
    draw.text((concept.width + 4, 4), "body + anchored first frames", fill=(0, 0, 0, 255))
    image.convert("RGB").save(output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", help="Defaults to <run>/qa/anchor-fit")
    parser.add_argument("--emotion", default="neutral", choices=REQUIRED_EMOTIONS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest_path = Path(args.manifest).expanduser().resolve()
    base_dir = manifest_path.parent
    run_dir = base_dir.parent
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else run_dir / "qa" / "anchor-fit"
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    canvas = manifest["canvas"]
    canvas_center = [int(canvas["width"]) / 2, int(canvas["height"]) / 2]
    anchors = manifest["anchors"]
    anchor_offsets = {
        name: [int(value["x"]) - canvas_center[0], int(value["y"]) - canvas_center[1]] for name, value in anchors.items()
    }

    frame_metrics: list[dict[str, Any]] = [alpha_bbox_info(base_dir / manifest["body"], base_dir)]
    first_frame_metrics: list[dict[str, Any]] = []
    for emotion in REQUIRED_EMOTIONS:
        entry = manifest["emotions"][emotion]
        for key in ("leftEye", "rightEye", "mouth"):
            metric = alpha_bbox_info(base_dir / entry[key][0], base_dir)
            metric["emotion"] = emotion
            metric["part"] = key
            first_frame_metrics.append(metric)
    frame_metrics.extend(first_frame_metrics)

    warnings: list[str] = []
    for metric in first_frame_metrics:
        delta = metric.get("center_delta")
        if delta and (abs(delta[0]) > 2 or abs(delta[1]) > 2):
            warnings.append(f"{metric['emotion']}.{metric['part']} content is off-center inside its frame: {delta}")
        if metric["part"] == "mouth":
            content_size = metric.get("content_size")
            if content_size and (content_size[0] < 24 or content_size[1] < 5):
                warnings.append(
                    f"{metric['emotion']}.mouth first frame may be too small for a 320x240 device preview: {content_size}"
                )

    overlay_path = output_dir / f"{args.emotion}-manifest-overlay.png"
    wrong_top_left_path = output_dir / f"{args.emotion}-wrong-top-left-diagnostic.png"
    comparison_path = output_dir / f"{args.emotion}-concept-vs-overlay.png"
    overlay_boxes = make_overlay(manifest, base_dir, overlay_path, args.emotion)
    make_overlay(manifest, base_dir, wrong_top_left_path, args.emotion, wrong_top_left=True)
    make_concept_comparison(manifest, base_dir, overlay_path, comparison_path, args.emotion)

    result = {
        "ok": True,
        "manifest": str(manifest_path),
        "emotion": args.emotion,
        "canvas_center": canvas_center,
        "anchors": anchors,
        "anchor_offsets_from_canvas_center": anchor_offsets,
        "overlay_boxes": overlay_boxes,
        "metrics": frame_metrics,
        "warnings": warnings,
        "artifacts": {
            "manifest_overlay": str(overlay_path),
            "wrong_top_left_diagnostic": str(wrong_top_left_path),
            "concept_vs_overlay": str(comparison_path),
        },
        "manual_gate": [
            "Open concept_vs_overlay and confirm eyes and mouth fit the intended face, not only the canvas.",
            "Reject the pack if the overlay looks materially worse than the concept face.",
            "Treat warnings as repair inputs, not as automatic acceptance.",
        ],
    }

    report_path = output_dir / "anchor-fit-report.json"
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"anchor_fit_report={report_path}")


if __name__ == "__main__":
    main()

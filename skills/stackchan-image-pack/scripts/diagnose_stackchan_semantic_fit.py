#!/usr/bin/env python3
"""Validate facial feature placement against an explicit StackChan face layout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


REQUIRED_EMOTIONS = ["neutral", "happy", "angry", "sad", "doubt", "sleepy"]
FEATURES = ["leftEye", "rightEye", "mouth"]


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"cannot read JSON {path}: {exc}") from exc


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def box_from_layout(value: dict[str, Any]) -> tuple[float, float, float, float]:
    return (
        float(value["x"]),
        float(value["y"]),
        float(value["x"]) + float(value["width"]),
        float(value["y"]) + float(value["height"]),
    )


def center_of_box(box: tuple[float, float, float, float]) -> tuple[float, float]:
    return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)


def size_of_box(box: tuple[float, float, float, float]) -> tuple[float, float]:
    return (box[2] - box[0], box[3] - box[1])


def tuple_box(box: list[int] | tuple[int, int, int, int]) -> tuple[float, float, float, float]:
    return (float(box[0]), float(box[1]), float(box[2]), float(box[3]))


def projected_alpha_box(image_path: Path, anchor: dict[str, Any]) -> dict[str, Any]:
    with Image.open(image_path) as opened:
        image = opened.convert("RGBA")
        alpha_box = image.getchannel("A").getbbox()
    if alpha_box is None:
        return {
            "path": str(image_path),
            "imageSize": list(image.size),
            "alphaBox": None,
            "projectedBox": None,
            "center": None,
            "contentSize": None,
        }

    left = float(anchor["x"]) - image.width / 2.0 + alpha_box[0]
    top = float(anchor["y"]) - image.height / 2.0 + alpha_box[1]
    right = float(anchor["x"]) - image.width / 2.0 + alpha_box[2]
    bottom = float(anchor["y"]) - image.height / 2.0 + alpha_box[3]
    projected = (left, top, right, bottom)
    return {
        "path": str(image_path),
        "imageSize": list(image.size),
        "alphaBox": list(alpha_box),
        "projectedBox": [round(value, 2) for value in projected],
        "center": [round(value, 2) for value in center_of_box(projected)],
        "contentSize": [round(value, 2) for value in size_of_box(projected)],
    }


def check_projected_box(
    *,
    emotion: str,
    feature: str,
    frame_index: int,
    metric: dict[str, Any],
    spec: dict[str, Any],
    errors: list[str],
    warnings: list[str],
) -> None:
    label = f"{emotion}.{feature}[{frame_index}]"
    projected_raw = metric.get("projectedBox")
    if projected_raw is None:
        errors.append(f"{label} is empty")
        return

    projected = tuple_box(projected_raw)
    center = center_of_box(projected)
    width, height = size_of_box(projected)

    target_center = spec.get("targetCenter")
    tolerance = spec.get("centerTolerance", {"x": 4, "y": 4})
    if target_center:
        dx = center[0] - float(target_center["x"])
        dy = center[1] - float(target_center["y"])
        if abs(dx) > float(tolerance.get("x", 4)) or abs(dy) > float(tolerance.get("y", 4)):
            errors.append(
                f"{label} center off target: actual=({center[0]:.1f},{center[1]:.1f}) "
                f"target=({float(target_center['x']):.1f},{float(target_center['y']):.1f}) "
                f"delta=({dx:.1f},{dy:.1f}) tolerance=({float(tolerance.get('x', 4)):.1f},{float(tolerance.get('y', 4)):.1f})"
            )

    slot = spec.get("slot")
    if slot:
        slot_box = box_from_layout(slot)
        overflow = float(spec.get("slotOverflowTolerance", 2))
        if (
            projected[0] < slot_box[0] - overflow
            or projected[1] < slot_box[1] - overflow
            or projected[2] > slot_box[2] + overflow
            or projected[3] > slot_box[3] + overflow
        ):
            errors.append(
                f"{label} leaves slot: projected={[round(v, 1) for v in projected]} "
                f"slot={[round(v, 1) for v in slot_box]} overflowTolerance={overflow:.1f}"
            )

    content_size = dict(spec.get("contentSize", {}))
    frame_content_sizes = spec.get("frameContentSize", {})
    frame_content_size = frame_content_sizes.get(str(frame_index)) if isinstance(frame_content_sizes, dict) else None
    if isinstance(frame_content_size, dict):
        content_size.update(frame_content_size)
    min_width = content_size.get("minWidth")
    max_width = content_size.get("maxWidth")
    min_height = content_size.get("minHeight")
    max_height = content_size.get("maxHeight")
    if min_width is not None and width < float(min_width):
        errors.append(f"{label} too narrow: {width:.1f}px < {float(min_width):.1f}px")
    if max_width is not None and width > float(max_width):
        errors.append(f"{label} too wide: {width:.1f}px > {float(max_width):.1f}px")
    if min_height is not None and height < float(min_height):
        errors.append(f"{label} too short: {height:.1f}px < {float(min_height):.1f}px")
    if max_height is not None and height > float(max_height):
        errors.append(f"{label} too tall: {height:.1f}px > {float(max_height):.1f}px")

    if feature == "mouth" and frame_index == 0 and width < 24:
        warnings.append(f"{label} closed mouth may be too small for 320x240 preview: {width:.1f}x{height:.1f}px")


def check_symmetry(metrics: dict[str, Any], layout: dict[str, Any], errors: list[str]) -> None:
    symmetry = layout.get("symmetry", {})
    if not symmetry:
        return
    neutral = metrics.get("neutral", {})
    left = neutral.get("leftEye", [{}])[0].get("center")
    right = neutral.get("rightEye", [{}])[0].get("center")
    if not left or not right:
        return

    distance = float(right[0]) - float(left[0])
    distance_spec = symmetry.get("eyeCenterDistance", {})
    min_distance = distance_spec.get("min")
    max_distance = distance_spec.get("max")
    if min_distance is not None and distance < float(min_distance):
        errors.append(f"neutral eye centers too close: {distance:.1f}px < {float(min_distance):.1f}px")
    if max_distance is not None and distance > float(max_distance):
        errors.append(f"neutral eye centers too far apart: {distance:.1f}px > {float(max_distance):.1f}px")

    y_delta_max = symmetry.get("eyeYDeltaMax")
    if y_delta_max is not None:
        y_delta = abs(float(right[1]) - float(left[1]))
        if y_delta > float(y_delta_max):
            errors.append(f"neutral eye y mismatch too large: {y_delta:.1f}px > {float(y_delta_max):.1f}px")


def draw_box(
    draw: ImageDraw.ImageDraw,
    box: tuple[float, float, float, float],
    label: str,
    color: tuple[int, int, int, int],
    *,
    width: int = 2,
) -> None:
    rounded = tuple(round(value) for value in box)
    draw.rectangle(rounded, outline=color, width=width)
    draw.text((rounded[0] + 2, rounded[1] + 2), label, fill=color)


def make_overlay(manifest: dict[str, Any], layout: dict[str, Any], base_dir: Path, metrics: dict[str, Any], output: Path) -> None:
    body = Image.open(base_dir / manifest["body"]).convert("RGBA")
    draw = ImageDraw.Draw(body)
    colors = {
        "faceBox": (0, 200, 0, 255),
        "leftEye": (255, 0, 0, 255),
        "rightEye": (0, 120, 255, 255),
        "mouth": (255, 0, 180, 255),
        "actual": (255, 220, 0, 255),
    }
    if "faceBox" in layout:
        draw_box(draw, box_from_layout(layout["faceBox"]), "faceBox", colors["faceBox"], width=1)
    for feature in FEATURES:
        spec = layout.get("parts", {}).get(feature, {})
        if "slot" in spec:
            draw_box(draw, box_from_layout(spec["slot"]), f"{feature} slot", colors[feature], width=2)
        projected = metrics.get("neutral", {}).get(feature, [{}])[0].get("projectedBox")
        if projected:
            draw_box(draw, tuple_box(projected), f"{feature} actual", colors["actual"], width=1)
    output.parent.mkdir(parents=True, exist_ok=True)
    body.convert("RGB").save(output)


def diagnose(manifest_path: Path, layout_path: Path, output_dir: Path) -> dict[str, Any]:
    manifest = read_json(manifest_path)
    layout = read_json(layout_path)
    base_dir = manifest_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, Any] = {}
    parts = layout.get("parts")
    if not isinstance(parts, dict):
        raise SystemExit("face layout must contain a parts object")

    anchors = manifest.get("anchors", {})
    for feature in FEATURES:
        if feature not in parts:
            errors.append(f"face layout missing part: {feature}")
        if feature not in anchors:
            errors.append(f"manifest missing anchor: {feature}")

    for emotion in REQUIRED_EMOTIONS:
        entry = manifest.get("emotions", {}).get(emotion)
        if not entry:
            errors.append(f"manifest missing emotion: {emotion}")
            continue
        metrics[emotion] = {}
        for feature in FEATURES:
            frames = entry.get(feature)
            if not isinstance(frames, list):
                errors.append(f"{emotion}.{feature} is not a frame list")
                continue
            metrics[emotion][feature] = []
            for index, rel_path in enumerate(frames):
                metric = projected_alpha_box(base_dir / rel_path, anchors.get(feature, {"x": 0, "y": 0}))
                metrics[emotion][feature].append(metric)
                if feature in parts:
                    check_projected_box(
                        emotion=emotion,
                        feature=feature,
                        frame_index=index,
                        metric=metric,
                        spec=parts[feature],
                        errors=errors,
                        warnings=warnings,
                    )

    check_symmetry(metrics, layout, errors)

    overlay_path = output_dir / "neutral-semantic-overlay.png"
    try:
        make_overlay(manifest, layout, base_dir, metrics, overlay_path)
    except Exception as exc:
        warnings.append(f"could not render semantic overlay: {exc}")

    result = {
        "ok": not errors,
        "manifest": str(manifest_path),
        "layout": str(layout_path),
        "errors": errors,
        "warnings": warnings,
        "metrics": metrics,
        "artifacts": {
            "neutral_semantic_overlay": str(overlay_path),
            "semantic_fit_report": str(output_dir / "semantic-fit-report.json"),
        },
        "manual_gate": [
            "Open neutral-semantic-overlay.png and confirm actual feature boxes sit inside the intended face slots.",
            "Reject the pack if automatic checks pass but the face still looks less appealing than the concept.",
            "Do not tune firmware offsets until this source-level semantic fit passes.",
        ],
    }
    write_json(output_dir / "semantic-fit-report.json", result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--layout", required=True)
    parser.add_argument("--output-dir", help="Defaults to <run>/qa/semantic-fit")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest_path = Path(args.manifest).expanduser().resolve()
    layout_path = Path(args.layout).expanduser().resolve()
    run_dir = manifest_path.parent.parent
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else run_dir / "qa" / "semantic-fit"
    result = diagnose(manifest_path, layout_path, output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

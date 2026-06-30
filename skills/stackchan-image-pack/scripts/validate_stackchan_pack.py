#!/usr/bin/env python3
"""Validate a finalized StackChan ImageAvatar pack manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


REQUIRED_EMOTIONS = ["neutral", "happy", "angry", "sad", "doubt", "sleepy"]
REQUIRED_DECORATORS = ["heart", "sweat", "anger", "tear", "dizzy"]


def has_alpha(image: Image.Image) -> bool:
    return image.mode in ("RGBA", "LA") or "transparency" in image.info


def open_image(path: Path, errors: list[str]) -> Image.Image | None:
    if not path.exists():
        errors.append(f"missing file: {path}")
        return None
    try:
        return Image.open(path)
    except Exception as exc:
        errors.append(f"cannot open image {path}: {exc}")
        return None


def check_image(path: Path, expected_size: tuple[int, int] | None, require_alpha: bool, errors: list[str], warnings: list[str]) -> None:
    image = open_image(path, errors)
    if image is None:
        return
    if expected_size and image.size != expected_size:
        errors.append(f"wrong size for {path}: expected {expected_size}, got {image.size}")
    if require_alpha and not has_alpha(image):
        errors.append(f"image lacks alpha channel: {path}")
    if image.size[0] <= 0 or image.size[1] <= 0:
        errors.append(f"invalid dimensions for {path}: {image.size}")
    if expected_size is None and max(image.size) > 256:
        warnings.append(f"large decorator or optional image, inspect manually: {path} {image.size}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--json-out")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest_path = Path(args.manifest).expanduser().resolve()
    base_dir = manifest_path.parent
    errors: list[str] = []
    warnings: list[str] = []

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"cannot read manifest: {exc}")

    canvas = manifest.get("canvas", {})
    canvas_size = (int(canvas.get("width", 320)), int(canvas.get("height", 240)))
    eye = manifest.get("frames", {}).get("eye", {})
    mouth = manifest.get("frames", {}).get("mouth", {})
    eye_size = (int(eye.get("width", 48)), int(eye.get("height", 48)))
    mouth_size = (int(mouth.get("width", 96)), int(mouth.get("height", 48)))
    eye_count = int(eye.get("count", 4))
    mouth_count = int(mouth.get("count", 4))

    body_path = base_dir / manifest.get("body", "")
    check_image(body_path, canvas_size, True, errors, warnings)

    emotions = manifest.get("emotions", {})
    for emotion in REQUIRED_EMOTIONS:
        if emotion not in emotions:
            errors.append(f"missing emotion: {emotion}")
            continue
        entry = emotions[emotion]
        if "concept" in entry:
            check_image(base_dir / entry["concept"], canvas_size, True, errors, warnings)
        for key, expected_count, expected_size in [
            ("leftEye", eye_count, eye_size),
            ("rightEye", eye_count, eye_size),
            ("mouth", mouth_count, mouth_size),
        ]:
            frames = entry.get(key)
            if not isinstance(frames, list):
                errors.append(f"{emotion}.{key} must be a list")
                continue
            if len(frames) != expected_count:
                errors.append(f"{emotion}.{key} wrong frame count: expected {expected_count}, got {len(frames)}")
            for rel_path in frames:
                check_image(base_dir / rel_path, expected_size, True, errors, warnings)

    decorators = manifest.get("decorators", {})
    for name in REQUIRED_DECORATORS:
        if name not in decorators:
            errors.append(f"missing decorator: {name}")
            continue
        check_image(base_dir / decorators[name], None, True, errors, warnings)

    result = {
        "ok": not errors,
        "manifest": str(manifest_path),
        "errors": errors,
        "warnings": warnings,
    }

    json_out = Path(args.json_out).expanduser().resolve() if args.json_out else base_dir.parent / "qa/validation.json"
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

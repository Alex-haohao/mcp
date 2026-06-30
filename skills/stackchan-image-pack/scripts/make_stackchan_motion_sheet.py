#!/usr/bin/env python3
"""Render all first-contract motion frames for StackChan ImageAvatar QA."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw


EMOTIONS = ["neutral", "happy", "angry", "sad", "doubt", "sleepy"]


def checker(size: tuple[int, int], cell: int = 12) -> Image.Image:
    image = Image.new("RGBA", size, "#ffffff")
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill="#eeeeee")
    return image


def paste_center(canvas: Image.Image, image: Image.Image, center: dict) -> None:
    x = int(float(center["x"]) - image.width / 2)
    y = int(float(center["y"]) - image.height / 2)
    canvas.alpha_composite(image, (x, y))


def load_rgba(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")


def render_frame(
    base_dir: Path,
    manifest: dict,
    body: Image.Image,
    emotion: str,
    *,
    eye_index: int,
    mouth_index: int,
) -> Image.Image:
    canvas = checker((int(manifest["canvas"]["width"]), int(manifest["canvas"]["height"])))
    canvas.alpha_composite(body, (0, 0))
    entry = manifest["emotions"][emotion]
    paste_center(canvas, load_rgba(base_dir / entry["leftEye"][eye_index]), manifest["anchors"]["leftEye"])
    paste_center(canvas, load_rgba(base_dir / entry["rightEye"][eye_index]), manifest["anchors"]["rightEye"])
    paste_center(canvas, load_rgba(base_dir / entry["mouth"][mouth_index]), manifest["anchors"]["mouth"])
    return canvas


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest_path = Path(args.manifest).expanduser().resolve()
    base_dir = manifest_path.parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    frame_count = int(manifest["frames"]["mouth"]["count"])
    if int(manifest["frames"]["eye"]["count"]) != frame_count:
        raise SystemExit("motion sheet expects matching eye and mouth frame counts")

    canvas_w = int(manifest["canvas"]["width"])
    canvas_h = int(manifest["canvas"]["height"])
    label_h = 24
    cols = frame_count * 2
    sheet = Image.new("RGBA", (cols * canvas_w, len(EMOTIONS) * (canvas_h + label_h)), "#ffffff")
    draw = ImageDraw.Draw(sheet)
    body = load_rgba(base_dir / manifest["body"])

    for row, emotion in enumerate(EMOTIONS):
        y0 = row * (canvas_h + label_h)
        for frame_index in range(frame_count):
            x0 = frame_index * canvas_w
            preview = render_frame(base_dir, manifest, body, emotion, eye_index=frame_index, mouth_index=0)
            sheet.alpha_composite(preview, (x0, y0 + label_h))
            draw.rectangle((x0, y0, x0 + canvas_w, y0 + label_h), fill="#222222")
            draw.text((x0 + 8, y0 + 5), f"{emotion} eye {frame_index}", fill="#ffffff")
        for frame_index in range(frame_count):
            x0 = (frame_count + frame_index) * canvas_w
            preview = render_frame(base_dir, manifest, body, emotion, eye_index=0, mouth_index=frame_index)
            sheet.alpha_composite(preview, (x0, y0 + label_h))
            draw.rectangle((x0, y0, x0 + canvas_w, y0 + label_h), fill="#222222")
            draw.text((x0 + 8, y0 + 5), f"{emotion} mouth {frame_index}", fill="#ffffff")

    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.convert("RGB").save(output)
    print(f"motion_sheet={output}")


if __name__ == "__main__":
    main()

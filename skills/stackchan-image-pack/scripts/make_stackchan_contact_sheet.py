#!/usr/bin/env python3
"""Render a StackChan ImageAvatar pack contact sheet."""

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
    x = int(center["x"] - image.width / 2)
    y = int(center["y"] - image.height / 2)
    canvas.alpha_composite(image, (x, y))


def load_rgba(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")


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

    canvas_w = int(manifest.get("canvas", {}).get("width", 320))
    canvas_h = int(manifest.get("canvas", {}).get("height", 240))
    label_h = 24
    cols = 3
    rows = 2
    sheet = Image.new("RGBA", (cols * canvas_w, rows * (canvas_h + label_h)), "#ffffff")
    draw = ImageDraw.Draw(sheet)
    body = load_rgba(base_dir / manifest["body"])

    for index, emotion in enumerate(EMOTIONS):
        col = index % cols
        row = index // cols
        x0 = col * canvas_w
        y0 = row * (canvas_h + label_h)
        preview = checker((canvas_w, canvas_h))
        preview.alpha_composite(body, (0, 0))
        entry = manifest["emotions"][emotion]
        left_eye = load_rgba(base_dir / entry["leftEye"][0])
        right_eye = load_rgba(base_dir / entry["rightEye"][0])
        mouth = load_rgba(base_dir / entry["mouth"][0])
        paste_center(preview, left_eye, manifest["anchors"]["leftEye"])
        paste_center(preview, right_eye, manifest["anchors"]["rightEye"])
        paste_center(preview, mouth, manifest["anchors"]["mouth"])
        sheet.alpha_composite(preview, (x0, y0 + label_h))
        draw.rectangle((x0, y0, x0 + canvas_w, y0 + label_h), fill="#222222")
        draw.text((x0 + 8, y0 + 5), emotion, fill="#ffffff")

    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.convert("RGB").save(output)
    print(f"contact_sheet={output}")


if __name__ == "__main__":
    main()

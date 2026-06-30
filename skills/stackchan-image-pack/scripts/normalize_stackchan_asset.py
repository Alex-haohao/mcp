#!/usr/bin/env python3
"""Normalize a generated StackChan asset to a contract size with alpha."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def parse_hex_color(value: str) -> tuple[int, int, int]:
    value = value.strip()
    if value.startswith("#"):
        value = value[1:]
    if len(value) != 6:
        raise argparse.ArgumentTypeError("expected color in #RRGGBB format")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def key_to_alpha(image: Image.Image, key: tuple[int, int, int], tolerance: int) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    for y in range(height):
        for x in range(width):
            red, green, blue, alpha = pixels[x, y]
            if abs(red - key[0]) <= tolerance and abs(green - key[1]) <= tolerance and abs(blue - key[2]) <= tolerance:
                pixels[x, y] = (0, 0, 0, 0)
            elif alpha == 0:
                pixels[x, y] = (0, 0, 0, 0)
    return rgba


def crop_content(image: Image.Image, padding: int) -> Image.Image:
    bbox = image.getbbox()
    if bbox is None:
        return image
    left, top, right, bottom = bbox
    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(image.width, right + padding)
    bottom = min(image.height, bottom + padding)
    return image.crop((left, top, right, bottom))


def resize_to_canvas(image: Image.Image, size: tuple[int, int], fit: str) -> Image.Image:
    target_w, target_h = size
    if fit == "stretch":
        resized = image.resize(size, Image.Resampling.NEAREST)
        canvas = Image.new("RGBA", size, (0, 0, 0, 0))
        canvas.alpha_composite(resized, (0, 0))
        return canvas

    scale = min(target_w / image.width, target_h / image.height)
    if fit == "cover":
        scale = max(target_w / image.width, target_h / image.height)
    resized_size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    resized = image.resize(resized_size, Image.Resampling.NEAREST)

    if fit == "cover":
        left = max(0, (resized.width - target_w) // 2)
        top = max(0, (resized.height - target_h) // 2)
        resized = resized.crop((left, top, left + target_w, top + target_h))
        canvas = Image.new("RGBA", size, (0, 0, 0, 0))
        canvas.alpha_composite(resized, (0, 0))
        return canvas

    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    x = (target_w - resized.width) // 2
    y = (target_h - resized.height) // 2
    canvas.alpha_composite(resized, (x, y))
    return canvas


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    parser.add_argument("--chroma-key", type=parse_hex_color, default=parse_hex_color("#FF00FF"))
    parser.add_argument("--tolerance", type=int, default=18)
    parser.add_argument("--crop-content", action="store_true")
    parser.add_argument("--padding", type=int, default=4)
    parser.add_argument("--fit", choices=["contain", "cover", "stretch"], default="contain")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = Path(args.input).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    with Image.open(source) as image:
        normalized = key_to_alpha(image, args.chroma_key, args.tolerance)
    if args.crop_content:
        normalized = crop_content(normalized, args.padding)
    normalized = resize_to_canvas(normalized, (args.width, args.height), args.fit)
    output.parent.mkdir(parents=True, exist_ok=True)
    normalized.save(output)
    print(f"normalized={output}")


if __name__ == "__main__":
    main()

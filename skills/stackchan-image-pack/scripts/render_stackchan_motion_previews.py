#!/usr/bin/env python3
"""Render animated QA previews for a finalized StackChan ImageAvatar pack."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw


EMOTIONS = ["neutral", "happy", "angry", "sad", "doubt", "sleepy"]
FRAME_SEQUENCE = [0, 1, 2, 3, 2, 1]
FRAME_DURATIONS = [150, 120, 120, 180, 120, 180]


def checker(size: tuple[int, int], cell: int = 12) -> Image.Image:
    image = Image.new("RGBA", size, "#ffffff")
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill="#eeeeee")
    return image


def load_rgba(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")


def paste_center(canvas: Image.Image, image: Image.Image, center: dict) -> None:
    x = int(center["x"] - image.width / 2)
    y = int(center["y"] - image.height / 2)
    canvas.alpha_composite(image, (x, y))


def render_emotion(manifest: dict, base_dir: Path, emotion: str) -> list[Image.Image]:
    canvas_w = int(manifest.get("canvas", {}).get("width", 320))
    canvas_h = int(manifest.get("canvas", {}).get("height", 240))
    body = load_rgba(base_dir / manifest["body"])
    entry = manifest["emotions"][emotion]
    frames: list[Image.Image] = []
    for frame_index in FRAME_SEQUENCE:
        frame = checker((canvas_w, canvas_h))
        frame.alpha_composite(body, (0, 0))
        left_eye = load_rgba(base_dir / entry["leftEye"][frame_index])
        right_eye = load_rgba(base_dir / entry["rightEye"][frame_index])
        mouth = load_rgba(base_dir / entry["mouth"][frame_index])
        paste_center(frame, left_eye, manifest["anchors"]["leftEye"])
        paste_center(frame, right_eye, manifest["anchors"]["rightEye"])
        paste_center(frame, mouth, manifest["anchors"]["mouth"])
        frames.append(frame.convert("RGB"))
    return frames


def save_gif(frames: list[Image.Image], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_DURATIONS,
        loop=0,
        optimize=False,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest_path = Path(args.manifest).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    base_dir = manifest_path.parent
    previews = []
    for emotion in EMOTIONS:
        frames = render_emotion(manifest, base_dir, emotion)
        output = output_dir / f"{emotion}.gif"
        save_gif(frames, output)
        previews.append({"emotion": emotion, "path": str(output), "frames": len(frames)})
    print(json.dumps({"ok": True, "output_dir": str(output_dir), "previews": previews}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

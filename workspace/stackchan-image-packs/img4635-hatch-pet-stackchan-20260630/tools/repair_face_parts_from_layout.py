#!/usr/bin/env python3
"""Repair IMG4635 eye and mouth strips from accepted concepts and face layout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image


EMOTIONS = ["neutral", "happy", "angry", "sad", "doubt", "sleepy"]
EYE_SIZE = (48, 48)
MOUTH_SIZE = (96, 48)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def box(value: dict[str, Any], margin: int = 0) -> tuple[int, int, int, int]:
    return (
        int(round(value["x"])) - margin,
        int(round(value["y"])) - margin,
        int(round(value["x"] + value["width"])) + margin,
        int(round(value["y"] + value["height"])) + margin,
    )


def target_center(spec: dict[str, Any]) -> tuple[float, float]:
    return (float(spec["targetCenter"]["x"]), float(spec["targetCenter"]["y"]))


def load_rgba(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")


def diff_extract(concept: Image.Image, body: Image.Image, crop_box: tuple[int, int, int, int]) -> Image.Image:
    concept_crop = concept.crop(crop_box).convert("RGBA")
    body_crop = body.crop(crop_box).convert("RGBA")
    out = Image.new("RGBA", concept_crop.size, (0, 0, 0, 0))
    cp = concept_crop.load()
    bp = body_crop.load()
    op = out.load()
    for y in range(concept_crop.height):
        for x in range(concept_crop.width):
            cr, cg, cb, ca = cp[x, y]
            br, bg, bb, ba = bp[x, y]
            if ca < 32:
                continue
            color_diff = abs(cr - br) + abs(cg - bg) + abs(cb - bb) + abs(ca - ba)
            is_feature_color = (
                (cb > 130 and cg > 60 and cr < 190)
                or (cr < 100 and cg < 100 and cb < 130)
                or (cr > 150 and cg < 130 and cb < 170)
            )
            if color_diff > 55 and is_feature_color:
                op[x, y] = (cr, cg, cb, ca)
    bbox = out.getchannel("A").getbbox()
    if bbox is None:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    return out.crop(bbox)


def resize_contain(image: Image.Image, max_size: tuple[int, int], *, min_width: int = 1) -> Image.Image:
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        return image
    image = image.crop(bbox)
    max_w, max_h = max_size
    scale = min(max_w / image.width, max_h / image.height)
    if image.width * scale < min_width:
        scale = min_width / image.width
    scale = min(scale, max_w / image.width, max_h / image.height)
    new_size = (max(1, int(round(image.width * scale))), max(1, int(round(image.height * scale))))
    return image.resize(new_size, Image.Resampling.LANCZOS)


def resize_exact(image: Image.Image, target_size: tuple[int, int]) -> Image.Image:
    bbox = image.getchannel("A").getbbox()
    if bbox is not None:
        image = image.crop(bbox)
    return image.resize(target_size, Image.Resampling.LANCZOS)


def place_in_frame(
    content: Image.Image,
    frame_size: tuple[int, int],
    *,
    anchor: tuple[int, int],
    desired_center: tuple[float, float],
) -> Image.Image:
    frame = Image.new("RGBA", frame_size, (0, 0, 0, 0))
    center_in_frame = (
        frame_size[0] / 2.0 + desired_center[0] - anchor[0],
        frame_size[1] / 2.0 + desired_center[1] - anchor[1],
    )
    left = int(round(center_in_frame[0] - content.width / 2.0))
    top = int(round(center_in_frame[1] - content.height / 2.0))
    frame.alpha_composite(content, (left, top))
    return frame


def eye_frames(base_eye: Image.Image, spec: dict[str, Any], anchor: tuple[int, int]) -> list[Image.Image]:
    max_w = int(spec["contentSize"]["maxWidth"])
    max_h = int(spec["contentSize"]["maxHeight"])
    base = resize_contain(base_eye, (max_w - 2, max_h - 2), min_width=18)
    frames = [base]
    for scale_y in (0.65, 0.36, 0.18):
        height = max(3, int(round(base.height * scale_y)))
        frames.append(base.resize((base.width, height), Image.Resampling.BICUBIC))
    return [place_in_frame(frame, EYE_SIZE, anchor=anchor, desired_center=target_center(spec)) for frame in frames]


def mouth_frames(existing_frames: list[Image.Image], concept_mouth: Image.Image, spec: dict[str, Any], anchor: tuple[int, int]) -> list[Image.Image]:
    desired_sizes = [(26, 7), (32, 12), (38, 16), (42, 20)]
    frames: list[Image.Image] = []
    for index, size in enumerate(desired_sizes):
        source = concept_mouth if index == 0 and concept_mouth.getchannel("A").getbbox() else existing_frames[index]
        content = resize_exact(source, size)
        frames.append(place_in_frame(content, MOUTH_SIZE, anchor=anchor, desired_center=target_center(spec)))
    return frames


def horizontal_strip(frames: list[Image.Image]) -> Image.Image:
    width = sum(frame.width for frame in frames)
    height = max(frame.height for frame in frames)
    strip = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    x = 0
    for frame in frames:
        strip.alpha_composite(frame, (x, 0))
        x += frame.width
    return strip


def update_manifest_template(run_dir: Path, layout: dict[str, Any]) -> None:
    template_path = run_dir / "final/manifest.template.json"
    manifest = read_json(template_path)
    manifest["anchors"] = {
        "leftEye": {
            "x": int(round(layout["parts"]["leftEye"]["targetCenter"]["x"])),
            "y": int(round(layout["parts"]["leftEye"]["targetCenter"]["y"])),
        },
        "rightEye": {
            "x": int(round(layout["parts"]["rightEye"]["targetCenter"]["x"])),
            "y": int(round(layout["parts"]["rightEye"]["targetCenter"]["y"])),
        },
        "mouth": {
            "x": int(round(layout["parts"]["mouth"]["targetCenter"]["x"])),
            "y": int(round(layout["parts"]["mouth"]["targetCenter"]["y"])),
        },
    }
    write_json(template_path, manifest)


def repair(run_dir: Path, layout_path: Path) -> dict[str, Any]:
    layout = read_json(layout_path)
    body = load_rgba(run_dir / "final/body/base.png")
    parts = layout["parts"]
    anchors = {
        name: (
            int(round(parts[name]["targetCenter"]["x"])),
            int(round(parts[name]["targetCenter"]["y"])),
        )
        for name in ("leftEye", "rightEye", "mouth")
    }
    decoded_dir = run_dir / "decoded/parts"
    repaired: list[str] = []
    for emotion in EMOTIONS:
        concept = load_rgba(run_dir / f"final/concepts/{emotion}.png")
        left_eye = diff_extract(concept, body, box(parts["leftEye"]["slot"], margin=3))
        right_eye = diff_extract(concept, body, box(parts["rightEye"]["slot"], margin=3))
        mouth = diff_extract(concept, body, box(parts["mouth"]["slot"], margin=3))

        left_frames = eye_frames(left_eye, parts["leftEye"], anchors["leftEye"])
        right_frames = eye_frames(right_eye, parts["rightEye"], anchors["rightEye"])

        existing_mouth_frames = [load_rgba(run_dir / f"final/mouth/{emotion}/{index}.png") for index in range(4)]
        mouth_strip_frames = mouth_frames(existing_mouth_frames, mouth, parts["mouth"], anchors["mouth"])

        outputs = {
            f"eyes-{emotion}-left.png": horizontal_strip(left_frames),
            f"eyes-{emotion}-right.png": horizontal_strip(right_frames),
            f"mouth-{emotion}.png": horizontal_strip(mouth_strip_frames),
        }
        for name, image in outputs.items():
            output = decoded_dir / name
            image.save(output)
            repaired.append(str(output))

    update_manifest_template(run_dir, layout)
    summary = {
        "ok": True,
        "runDir": str(run_dir),
        "layout": str(layout_path),
        "repaired": repaired,
        "policy": "concept-derived eye frame0 plus deterministic blink compression; mouth frames resized into the explicit face slot",
    }
    write_json(run_dir / "qa/semantic-fit/repair-summary.json", summary)
    write_json(
        run_dir / "qa/postprocess-summary.json",
        {
            "ok": True,
            "run_dir": str(run_dir),
            "mode": "face-layout-repair",
            "layout": str(layout_path),
            "processed_count": len(repaired),
            "processed": [
                {
                    "path": path,
                    "operation": "repair from accepted concept face slot",
                }
                for path in repaired
            ],
            "policy": (
                "The generic chroma-key postprocess step is intentionally not rerun after "
                "face-slot repair because it recenters strips globally and can invalidate "
                "the accepted semantic fit. This summary records the deterministic repair "
                "postprocess that produced the decoded assets used by finalization."
            ),
        },
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--layout", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = repair(Path(args.run_dir).expanduser().resolve(), Path(args.layout).expanduser().resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

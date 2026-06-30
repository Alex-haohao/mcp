#!/usr/bin/env python3
"""Postprocess generated StackChan assets from recorded source images."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from PIL import Image


CANVAS_SIZE = (320, 240)
EYE_STRIP_SIZE = (192, 48)
EYE_FRAME_SIZE = (48, 48)
MOUTH_STRIP_SIZE = (384, 48)
MOUTH_FRAME_SIZE = (96, 48)
DECORATOR_SIZE = (96, 96)
FRAME_COUNT = 4


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"cannot read JSON {path}: {exc}") from exc


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_hex_color(value: str) -> tuple[int, int, int]:
    value = value.strip()
    if value.startswith("#"):
        value = value[1:]
    if len(value) != 6:
        raise argparse.ArgumentTypeError("expected color in #RRGGBB format")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def chroma_key_from_request(run_dir: Path) -> tuple[int, int, int]:
    request_path = run_dir / "pack_request.json"
    if not request_path.exists():
        return parse_hex_color("#00FF00")
    request = read_json(request_path)
    chroma = request.get("chroma_key", {})
    if isinstance(chroma, dict) and isinstance(chroma.get("hex"), str):
        return parse_hex_color(chroma["hex"])
    return parse_hex_color("#00FF00")


def key_to_alpha(image: Image.Image, key: tuple[int, int, int], tolerance: int) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
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
    return image.crop(
        (
            max(0, left - padding),
            max(0, top - padding),
            min(image.width, right + padding),
            min(image.height, bottom + padding),
        )
    )


def resize_contain(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    scale = min(target_w / image.width, target_h / image.height)
    resized_size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    resized = image.resize(resized_size, Image.Resampling.NEAREST)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    canvas.alpha_composite(resized, ((target_w - resized.width) // 2, (target_h - resized.height) // 2))
    return canvas


def normalize(source: Path, output: Path, size: tuple[int, int], key: tuple[int, int, int], tolerance: int, padding: int) -> None:
    with Image.open(source) as image:
        keyed = key_to_alpha(image, key, tolerance)
    normalized = resize_contain(crop_content(keyed, padding), size)
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_name(output.stem + ".tmp.png")
    normalized.save(tmp)
    shutil.move(str(tmp), output)


def center_strip_frames(path: Path, frame_size: tuple[int, int]) -> None:
    with Image.open(path) as image:
        strip = image.convert("RGBA")
    frame_w, frame_h = frame_size
    expected_size = (frame_w * FRAME_COUNT, frame_h)
    if strip.size != expected_size:
        raise SystemExit(f"wrong strip size for {path}: expected {expected_size}, got {strip.size}")
    centered = Image.new("RGBA", expected_size, (0, 0, 0, 0))
    for index in range(FRAME_COUNT):
        frame = strip.crop((index * frame_w, 0, (index + 1) * frame_w, frame_h))
        bbox = frame.getbbox()
        if bbox is None:
            continue
        content = frame.crop(bbox)
        max_w = frame_w - 4
        max_h = frame_h - 4
        if content.width > max_w or content.height > max_h:
            scale = min(max_w / content.width, max_h / content.height)
            content = content.resize(
                (max(1, round(content.width * scale)), max(1, round(content.height * scale))),
                Image.Resampling.NEAREST,
            )
        x = index * frame_w + (frame_w - content.width) // 2
        y = (frame_h - content.height) // 2
        centered.alpha_composite(content, (x, y))
    tmp = path.with_name(path.stem + ".tmp.png")
    centered.save(tmp)
    shutil.move(str(tmp), path)


def resolve_source(job: dict, run_dir: Path, allow_decoded_fallback: bool) -> Path:
    raw_source = job.get("source_path")
    if isinstance(raw_source, str) and raw_source:
        source = Path(raw_source).expanduser()
        if not source.is_absolute():
            source = run_dir / source
        if source.is_file():
            return source.resolve()
    if allow_decoded_fallback:
        output = run_dir / str(job.get("output_path", ""))
        if output.is_file():
            return output.resolve()
    raise SystemExit(f"missing source_path for completed job: {job.get('id')}")


def process_job(job: dict, run_dir: Path, key: tuple[int, int, int], tolerance: int, allow_decoded_fallback: bool) -> dict | None:
    kind = job.get("kind")
    if job.get("status") != "complete" or not job.get("output_path"):
        return None
    if kind not in {"emotion-concept", "body", "eye-strip", "mouth-strip", "decorator"}:
        return None

    output = (run_dir / str(job["output_path"])).resolve()
    source = resolve_source(job, run_dir, allow_decoded_fallback)
    frame_size = None
    if kind == "emotion-concept":
        size = CANVAS_SIZE
        padding = 8
    elif kind == "body":
        size = CANVAS_SIZE
        padding = 8
    elif kind == "eye-strip":
        size = EYE_STRIP_SIZE
        frame_size = EYE_FRAME_SIZE
        padding = 2
    elif kind == "mouth-strip":
        size = MOUTH_STRIP_SIZE
        frame_size = MOUTH_FRAME_SIZE
        padding = 2
    else:
        size = DECORATOR_SIZE
        padding = 8

    normalize(source, output, size, key, tolerance, padding)
    if frame_size is not None:
        center_strip_frames(output, frame_size)
    return {"job_id": job["id"], "kind": kind, "source": str(source), "output": str(output), "size": list(size)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--chroma-key", type=parse_hex_color)
    parser.add_argument("--tolerance", type=int, default=72)
    parser.add_argument("--allow-decoded-fallback", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = Path(args.run_dir).expanduser().resolve()
    if not run_dir.exists():
        raise SystemExit(f"run dir does not exist: {run_dir}")
    manifest = read_json(run_dir / "imagegen-jobs.json")
    key = args.chroma_key or chroma_key_from_request(run_dir)
    processed = []
    for job in manifest.get("jobs", []):
        if not isinstance(job, dict):
            continue
        result = process_job(job, run_dir, key, args.tolerance, args.allow_decoded_fallback)
        if result:
            processed.append(result)
    summary = {
        "ok": True,
        "run_dir": str(run_dir),
        "chroma_key": f"#{key[0]:02X}{key[1]:02X}{key[2]:02X}",
        "tolerance": args.tolerance,
        "processed_count": len(processed),
        "processed": processed,
    }
    write_json(run_dir / "qa/postprocess-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

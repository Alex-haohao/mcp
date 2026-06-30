#!/usr/bin/env python3
"""Finalize a StackChan ImageAvatar pack from generated component outputs."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from PIL import Image


EMOTIONS = ["neutral", "happy", "angry", "sad", "doubt", "sleepy"]
DECORATORS = ["heart", "sweat", "anger", "tear", "dizzy"]
CANVAS_SIZE = (320, 240)
EYE_FRAME_SIZE = (48, 48)
MOUTH_FRAME_SIZE = (96, 48)
FRAME_COUNT = 4


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"cannot read JSON {path}: {exc}") from exc


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def assert_can_write(path: Path, force: bool) -> None:
    if path.exists() and not force:
        raise SystemExit(f"refusing to overwrite existing file without --force: {path}")


def open_checked(path: Path, expected_size: tuple[int, int]) -> Image.Image:
    if not path.exists():
        raise SystemExit(f"missing generated asset: {path}")
    try:
        image = Image.open(path)
        image.load()
    except Exception as exc:
        raise SystemExit(f"cannot open generated asset {path}: {exc}") from exc
    if image.size != expected_size:
        raise SystemExit(f"wrong size for {path}: expected {expected_size}, got {image.size}")
    return image


def copy_checked(src: Path, dst: Path, expected_size: tuple[int, int], force: bool) -> str:
    open_checked(src, expected_size).close()
    assert_can_write(dst, force)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return str(dst)


def split_strip(src: Path, strip_dst: Path, frame_dir: Path, prefix: str, frame_size: tuple[int, int], force: bool) -> list[str]:
    frame_w, frame_h = frame_size
    strip_size = (frame_w * FRAME_COUNT, frame_h)
    image = open_checked(src, strip_size)

    assert_can_write(strip_dst, force)
    strip_dst.parent.mkdir(parents=True, exist_ok=True)
    image.save(strip_dst)

    frame_paths: list[str] = []
    for index in range(FRAME_COUNT):
        dst = frame_dir / f"{prefix}{index}.png"
        assert_can_write(dst, force)
        dst.parent.mkdir(parents=True, exist_ok=True)
        frame = image.crop((index * frame_w, 0, (index + 1) * frame_w, frame_h))
        frame.save(dst)
        frame_paths.append(str(dst))
    image.close()
    return frame_paths


def finalize(run_dir: Path, force: bool) -> dict:
    final_dir = run_dir / "final"
    decoded_dir = run_dir / "decoded"
    qa_dir = run_dir / "qa"
    template_path = final_dir / "manifest.template.json"
    manifest_path = final_dir / "manifest.json"
    manifest = read_json(template_path)

    copied: list[str] = []
    split: list[dict] = []

    copied.append(copy_checked(decoded_dir / "parts/body-base.png", final_dir / "body/base.png", CANVAS_SIZE, force))

    for emotion in EMOTIONS:
        copied.append(copy_checked(decoded_dir / f"concepts/{emotion}.png", final_dir / f"concepts/{emotion}.png", CANVAS_SIZE, force))

        left_frames = split_strip(
            decoded_dir / f"parts/eyes-{emotion}-left.png",
            final_dir / f"eyes/{emotion}/left-strip.png",
            final_dir / f"eyes/{emotion}",
            "left_",
            EYE_FRAME_SIZE,
            force,
        )
        right_frames = split_strip(
            decoded_dir / f"parts/eyes-{emotion}-right.png",
            final_dir / f"eyes/{emotion}/right-strip.png",
            final_dir / f"eyes/{emotion}",
            "right_",
            EYE_FRAME_SIZE,
            force,
        )
        mouth_frames = split_strip(
            decoded_dir / f"parts/mouth-{emotion}.png",
            final_dir / f"mouth/{emotion}/strip.png",
            final_dir / f"mouth/{emotion}",
            "",
            MOUTH_FRAME_SIZE,
            force,
        )
        split.extend(
            [
                {"emotion": emotion, "part": "leftEye", "frames": left_frames},
                {"emotion": emotion, "part": "rightEye", "frames": right_frames},
                {"emotion": emotion, "part": "mouth", "frames": mouth_frames},
            ]
        )

    for decorator in DECORATORS:
        src = decoded_dir / f"decorators/{decorator}.png"
        if not src.exists():
            raise SystemExit(f"missing generated asset: {src}")
        with Image.open(src) as image:
            size = image.size
            if image.width <= 0 or image.height <= 0:
                raise SystemExit(f"invalid dimensions for {src}: {image.size}")
            if image.width > 96 or image.height > 96:
                raise SystemExit(f"decorator too large for {src}: expected <= 96x96, got {image.size}")
        copied.append(copy_checked(src, final_dir / f"decorators/{decorator}.png", size, force))

    assert_can_write(manifest_path, force)
    write_json(manifest_path, manifest)

    summary = {
        "ok": True,
        "run_dir": str(run_dir),
        "manifest": str(manifest_path),
        "copied": copied,
        "split": split,
    }
    write_json(qa_dir / "finalize-summary.json", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = Path(args.run_dir).expanduser().resolve()
    if not run_dir.exists():
        raise SystemExit(f"run dir does not exist: {run_dir}")
    summary = finalize(run_dir, args.force)
    print(f"manifest={summary['manifest']}")
    print(f"finalize_summary={run_dir / 'qa/finalize-summary.json'}")


if __name__ == "__main__":
    main()

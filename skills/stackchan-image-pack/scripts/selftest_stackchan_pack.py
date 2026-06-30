#!/usr/bin/env python3
"""Smoke-test the StackChan image-pack scripts with deterministic PNG fixtures."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw

import postprocess_stackchan_assets


EMOTIONS = ["neutral", "happy", "angry", "sad", "doubt", "sleepy"]
DECORATORS = ["heart", "sweat", "anger", "tear", "dizzy"]
SCRIPT_DIR = Path(__file__).resolve().parent


def save_fixture(path: Path, size: tuple[int, int], label: str, color: tuple[int, int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    inset = max(2, min(size) // 8)
    draw.rounded_rectangle(
        (inset, inset, size[0] - inset - 1, size[1] - inset - 1),
        radius=min(size) // 6,
        fill=color,
        outline=(30, 30, 30, 255),
    )
    draw.text((inset + 2, inset + 2), label[:8], fill=(255, 255, 255, 255))
    image.save(path)


def save_chroma_fixture(path: Path, size: tuple[int, int], label: str, color: tuple[int, int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", size, (0, 255, 0, 255))
    draw = ImageDraw.Draw(image)
    inset_x = max(4, size[0] // 6)
    inset_y = max(4, size[1] // 5)
    draw.rounded_rectangle(
        (inset_x + 7, inset_y, size[0] - inset_x - 1, size[1] - inset_y - 1),
        radius=max(3, min(size) // 8),
        fill=color,
        outline=(30, 30, 30, 255),
    )
    draw.text((inset_x + 12, inset_y + 4), label[:8], fill=(255, 255, 255, 255))
    image.save(path)


def save_chroma_strip_fixture(
    path: Path,
    frame_size: tuple[int, int],
    count: int,
    label: str,
    color: tuple[int, int, int, int],
) -> None:
    scale = 2
    frame_w, frame_h = frame_size
    image = Image.new("RGBA", (frame_w * count * scale, frame_h * scale), (0, 255, 0, 255))
    draw = ImageDraw.Draw(image)
    for index in range(count):
        slot_x = index * frame_w * scale
        content_w = max(8, int(frame_w * scale * (0.52 - index * 0.07)))
        content_h = max(6, int(frame_h * scale * (0.48 - index * 0.05)))
        x0 = slot_x + (frame_w * scale - content_w) // 2
        y0 = (frame_h * scale - content_h) // 2
        draw.rounded_rectangle(
            (x0, y0, x0 + content_w, y0 + content_h),
            radius=max(2, content_h // 5),
            fill=color,
            outline=(30, 30, 30, 255),
        )
        draw.text((x0 + 2, y0 + 1), f"{label[:1]}{index}", fill=(255, 255, 255, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def make_fixtures(run_dir: Path) -> None:
    colors = [
        (56, 120, 202, 220),
        (229, 159, 67, 220),
        (202, 63, 80, 220),
        (82, 145, 104, 220),
        (134, 94, 177, 220),
        (88, 88, 88, 220),
    ]
    for index, emotion in enumerate(EMOTIONS):
        color = colors[index]
        save_fixture(run_dir / f"decoded/concepts/{emotion}.png", (320, 240), emotion, color)
        save_fixture(run_dir / f"decoded/parts/mouth-{emotion}.png", (384, 48), emotion, color)
        for side in ["left", "right"]:
            save_fixture(run_dir / f"decoded/parts/eyes-{emotion}-{side}.png", (192, 48), f"{emotion}-{side}", color)
    save_fixture(run_dir / "decoded/parts/body-base.png", (320, 240), "body", (45, 45, 45, 220))
    for index, decorator in enumerate(DECORATORS):
        save_fixture(run_dir / f"decoded/decorators/{decorator}.png", (64, 64), decorator, colors[index])


def make_generated_source_fixtures(run_dir: Path) -> None:
    colors = [
        (56, 120, 202, 255),
        (229, 159, 67, 255),
        (202, 63, 80, 255),
        (82, 145, 104, 255),
        (134, 94, 177, 255),
        (88, 88, 88, 255),
    ]
    manifest_path = run_dir / "imagegen-jobs.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    completed_at = datetime.now(timezone.utc).isoformat()
    color_by_emotion = dict(zip(EMOTIONS, colors))
    for job in manifest["jobs"]:
        kind = job.get("kind")
        job_id = job["id"]
        if kind not in {"emotion-concept", "body", "eye-strip", "mouth-strip", "decorator"}:
            continue
        output = run_dir / job["output_path"]
        save_fixture(output, (16, 16), "bad", (255, 0, 0, 255))
        source = run_dir / "qa/generated-source" / f"{job_id}.png"
        if kind == "emotion-concept":
            emotion = job_id.removeprefix("concept-")
            save_chroma_fixture(source, (640, 480), emotion, color_by_emotion[emotion])
        elif kind == "body":
            save_chroma_fixture(source, (640, 480), "body", (45, 45, 45, 255))
        elif kind == "eye-strip":
            emotion = job_id.split("-")[1]
            save_chroma_strip_fixture(source, (48, 48), 4, "eye", color_by_emotion[emotion])
        elif kind == "mouth-strip":
            emotion = job_id.removeprefix("mouth-")
            save_chroma_strip_fixture(source, (96, 48), 4, "mouth", color_by_emotion[emotion])
        elif kind == "decorator":
            decorator = job_id.removeprefix("decorator-")
            save_chroma_fixture(source, (128, 128), decorator, colors[DECORATORS.index(decorator)])
        job.update({"status": "complete", "source_path": str(source), "completed_at": completed_at})
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_cmd(args: list[str]) -> None:
    subprocess.run(args, check=True)


def assert_hatch_pet_alignment(run_dir: Path) -> None:
    request = json.loads((run_dir / "pack_request.json").read_text(encoding="utf-8"))
    assert request["style_preset"] == "pixel"
    assert "Pixel-art-adjacent" in request["style_contract"]
    assert "hatch-pet" in request["style_contract"]

    prompt = (run_dir / "prompts/parts/eyes-neutral-left.md").read_text(encoding="utf-8")
    assert "horizontal sprite strip" in prompt
    assert "layout guide" in prompt
    assert "Pixel-art-adjacent" in prompt

    manifest = json.loads((run_dir / "imagegen-jobs.json").read_text(encoding="utf-8"))
    assert manifest["primary_generation_skill"] == "$imagegen"
    canonical_jobs = [job for job in manifest["jobs"] if job["id"] == "canonical-style"]
    assert len(canonical_jobs) == 1
    assert canonical_jobs[0]["kind"] == "manual-selection"
    concept_jobs = [job for job in manifest["jobs"] if job["kind"] in {"emotion-concept", "body", "eye-strip", "mouth-strip", "decorator"}]
    assert concept_jobs
    for job in concept_jobs:
        assert "canonical-style" in job["depends_on"]
    strip_jobs = [job for job in manifest["jobs"] if job["kind"] in {"eye-strip", "mouth-strip"}]
    assert strip_jobs
    for job in strip_jobs:
        assert job["generation_skill"] == "$imagegen"
        assert job["retry_prompt_file"]
        roles = " ".join(image["role"] for image in job["input_images"])
        assert "layout guide" in roles
        assert "canonical" in roles
        assert "face-proportion" in roles

    eye_prompt = (run_dir / "prompts/parts/eyes-neutral-left.md").read_text(encoding="utf-8")
    mouth_prompt = (run_dir / "prompts/parts/mouth-neutral.md").read_text(encoding="utf-8")
    for prompt_text in (eye_prompt, mouth_prompt):
        assert "upstream generation contract" in prompt_text
        assert "Regenerate this component" in prompt_text
        assert "Do not rely on postprocessing" in prompt_text


def assert_canonical_recorded(run_dir: Path) -> None:
    manifest = json.loads((run_dir / "imagegen-jobs.json").read_text(encoding="utf-8"))
    jobs = {job["id"]: job for job in manifest["jobs"]}
    assert jobs["neutral-style-1"]["status"] == "complete"
    assert jobs["canonical-style"]["status"] == "complete"
    assert jobs["canonical-style"]["source_job_id"] == "neutral-style-1"
    assert (run_dir / "references/canonical-style.png").exists()
    assert (run_dir / "decoded/concepts/neutral-style-1.png").exists()


def assert_manifest_complete(manifest_path: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert list(manifest["emotions"].keys()) == EMOTIONS
    for emotion in EMOTIONS:
        entry = manifest["emotions"][emotion]
        assert len(entry["leftEye"]) == 4
        assert len(entry["rightEye"]) == 4
        assert len(entry["mouth"]) == 4
        for key in ["leftEye", "rightEye", "mouth"]:
            for rel_path in entry[key]:
                assert (manifest_path.parent / rel_path).exists(), rel_path
    for decorator in DECORATORS:
        assert (manifest_path.parent / manifest["decorators"][decorator]).exists(), decorator


def assert_no_chroma_residue(image_path: Path) -> None:
    with Image.open(image_path) as image:
        rgba = image.convert("RGBA")
    residue = 0
    data = rgba.tobytes()
    for index in range(0, len(data), 4):
        red, green, blue, alpha = data[index : index + 4]
        if alpha > 0 and red < 80 and green > 180 and blue < 100:
            residue += 1
    assert residue == 0, f"chroma residue in {image_path}: {residue} pixels"


def assert_frame_content_centered(strip_path: Path, frame_size: tuple[int, int], count: int = 4) -> None:
    with Image.open(strip_path) as image:
        strip = image.convert("RGBA")
    frame_w, frame_h = frame_size
    assert strip.size == (frame_w * count, frame_h)
    for index in range(count):
        frame = strip.crop((index * frame_w, 0, (index + 1) * frame_w, frame_h))
        bbox = frame.getbbox()
        assert bbox is not None, f"empty frame {index} in {strip_path}"
        center_x = (bbox[0] + bbox[2]) / 2
        center_y = (bbox[1] + bbox[3]) / 2
        assert abs(center_x - frame_w / 2) <= 3, (strip_path, index, bbox)
        assert abs(center_y - frame_h / 2) <= 3, (strip_path, index, bbox)


def assert_postprocess_preserves_strip_layout(tmp_root: Path) -> None:
    source = tmp_root / "preserve-source.png"
    output = tmp_root / "preserve-output.png"
    image = Image.new("RGBA", (384, 96), (0, 255, 0, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 30, 60, 58), fill=(40, 80, 180, 255))
    image.save(source)

    postprocess_stackchan_assets.normalize(source, output, (192, 48), (0, 255, 0), 0)

    with Image.open(output) as opened:
        alpha_box = opened.convert("RGBA").getchannel("A").getbbox()
    assert alpha_box is not None
    assert alpha_box[0] <= 12, alpha_box
    assert alpha_box[2] <= 32, alpha_box


def assert_postprocessed_decoded_assets(run_dir: Path) -> None:
    body = run_dir / "decoded/parts/body-base.png"
    with Image.open(body) as image:
        assert image.size == (320, 240)
        assert image.mode == "RGBA"
        bbox = image.getbbox()
        assert bbox is not None
        assert abs(((bbox[0] + bbox[2]) / 2) - 160) <= 8
    assert_no_chroma_residue(body)
    for emotion in EMOTIONS:
        assert_no_chroma_residue(run_dir / f"decoded/concepts/{emotion}.png")
        assert_frame_content_centered(run_dir / f"decoded/parts/eyes-{emotion}-left.png", (48, 48))
        assert_frame_content_centered(run_dir / f"decoded/parts/eyes-{emotion}-right.png", (48, 48))
        assert_frame_content_centered(run_dir / f"decoded/parts/mouth-{emotion}.png", (96, 48))
    for decorator in DECORATORS:
        path = run_dir / f"decoded/decorators/{decorator}.png"
        with Image.open(path) as image:
            assert image.size == (96, 96)
            assert image.mode == "RGBA"
        assert_no_chroma_residue(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tmp_root = Path(tempfile.mkdtemp(prefix="stackchan-pack-selftest-"))
    try:
        run_dir = tmp_root / "run"
        assert_postprocess_preserves_strip_layout(tmp_root)
        run_cmd(
            [
                sys.executable,
                str(SCRIPT_DIR / "prepare_stackchan_pack_run.py"),
                "--pack-name",
                "Selftest StackChan",
                "--description",
                "Deterministic self-test pack",
                "--output-dir",
                str(run_dir),
                "--force",
            ]
        )
        assert_hatch_pet_alignment(run_dir)
        style_source = run_dir / "qa/style-source.png"
        save_fixture(style_source, (320, 240), "style", (56, 120, 202, 220))
        run_cmd(
            [
                sys.executable,
                str(SCRIPT_DIR / "record_stackchan_job_output.py"),
                "--run-dir",
                str(run_dir),
                "--job-id",
                "neutral-style-1",
                "--source",
                str(style_source),
                "--promote-canonical",
                "--force",
            ]
        )
        assert_canonical_recorded(run_dir)
        make_fixtures(run_dir)
        make_generated_source_fixtures(run_dir)
        run_cmd(
            [
                sys.executable,
                str(SCRIPT_DIR / "postprocess_stackchan_assets.py"),
                "--run-dir",
                str(run_dir),
                "--chroma-key",
                "#00FF00",
            ]
        )
        assert_postprocessed_decoded_assets(run_dir)
        run_cmd([sys.executable, str(SCRIPT_DIR / "finalize_stackchan_pack.py"), "--run-dir", str(run_dir), "--force"])
        manifest_path = run_dir / "final/manifest.json"
        assert_manifest_complete(manifest_path)
        run_cmd([sys.executable, str(SCRIPT_DIR / "validate_stackchan_pack.py"), "--manifest", str(manifest_path)])
        run_cmd(
            [
                sys.executable,
                str(SCRIPT_DIR / "make_stackchan_contact_sheet.py"),
                "--manifest",
                str(manifest_path),
                "--output",
                str(run_dir / "qa/contact-sheet.png"),
            ]
        )
        run_cmd(
            [
                sys.executable,
                str(SCRIPT_DIR / "render_stackchan_motion_previews.py"),
                "--manifest",
                str(manifest_path),
                "--output-dir",
                str(run_dir / "qa/previews"),
            ]
        )
        for emotion in EMOTIONS:
            assert (run_dir / f"qa/previews/{emotion}.gif").exists()
        if args.keep:
            print(f"selftest=ok kept_run_dir={run_dir}")
        else:
            print("selftest=ok")
    finally:
        if not args.keep:
            shutil.rmtree(tmp_root, ignore_errors=True)


if __name__ == "__main__":
    main()

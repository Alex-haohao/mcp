#!/usr/bin/env python3
"""Record a selected $imagegen output in a StackChan image-pack run."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"cannot read JSON {path}: {exc}") from exc


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def find_job(manifest: dict, job_id: str) -> dict:
    for job in manifest.get("jobs", []):
        if job.get("id") == job_id:
            return job
    raise SystemExit(f"unknown job id: {job_id}")


def complete_deps(manifest: dict) -> set[str]:
    return {
        job["id"]
        for job in manifest.get("jobs", [])
        if isinstance(job, dict) and job.get("status") == "complete" and isinstance(job.get("id"), str)
    }


def copy_output(source: Path, destination: Path, force: bool) -> None:
    if not source.is_file():
        raise SystemExit(f"source image not found: {source}")
    if destination.exists() and not force:
        raise SystemExit(f"refusing to overwrite existing output without --force: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != destination.resolve():
        shutil.copy2(source, destination)


def maybe_cleanup_source(source: Path) -> None:
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    generated_root = codex_home / "generated_images"
    try:
        source.relative_to(generated_root)
    except ValueError:
        return
    source.unlink(missing_ok=True)
    try:
        source.parent.rmdir()
    except OSError:
        pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--promote-canonical", action="store_true")
    parser.add_argument("--allow-incomplete-deps", action="store_true")
    parser.add_argument("--cleanup-generated-source", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = Path(args.run_dir).expanduser().resolve()
    source = Path(args.source).expanduser().resolve()
    manifest_path = run_dir / "imagegen-jobs.json"
    manifest = read_json(manifest_path)
    job = find_job(manifest, args.job_id)

    incomplete = sorted(set(job.get("depends_on", [])) - complete_deps(manifest))
    if incomplete and not args.allow_incomplete_deps:
        raise SystemExit(f"job {args.job_id} has incomplete dependencies: {', '.join(incomplete)}")

    output_path = run_dir / str(job.get("output_path", ""))
    copy_output(source, output_path, args.force)
    completed_at = datetime.now(timezone.utc).isoformat()
    job.update(
        {
            "status": "complete",
            "source_path": str(source),
            "completed_at": completed_at,
        }
    )

    canonical_path = None
    if args.promote_canonical:
        if job.get("kind") != "style-candidate":
            raise SystemExit("--promote-canonical can only be used with a style-candidate job")
        canonical_job = find_job(manifest, "canonical-style")
        canonical_path = run_dir / str(canonical_job.get("output_path", "references/canonical-style.png"))
        copy_output(output_path, canonical_path, args.force)
        canonical_job.update(
            {
                "status": "complete",
                "source_job_id": args.job_id,
                "source_path": str(output_path),
                "completed_at": completed_at,
            }
        )

    write_json(manifest_path, manifest)
    if args.cleanup_generated_source:
        maybe_cleanup_source(source)

    result = {
        "ok": True,
        "job_id": args.job_id,
        "output": str(output_path),
        "canonical": str(canonical_path) if canonical_path else "",
        "manifest": str(manifest_path),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

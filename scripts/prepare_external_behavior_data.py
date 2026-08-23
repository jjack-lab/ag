"""Inspect, acquire, and prepare provenance-safe external behavior data."""

import argparse
import csv
import json
from pathlib import Path
from typing import Iterable, Mapping

from cattle_health_app.behavior.cbvd5 import map_cbvd5_labels, parse_ava_annotations
from cattle_health_app.behavior.external_clips import (
    assign_groups,
    deterministic_class_cap,
    make_clip_record,
    write_clip_manifest,
)
from cattle_health_app.behavior.external_download import (
    DownloadBlocked,
    RemoteFileSpec,
    acquire_file,
    append_operation,
    sha256_file,
)
from cattle_health_app.behavior.external_registry import load_registry


DEFAULT_SEED = 20260823


def _inside_project(path: Path, project_root: Path, field: str) -> Path:
    resolved = path.expanduser().resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError as exc:
        raise ValueError("{} must stay inside project_root".format(field)) from exc
    return resolved


def _load_inventory(path: Path) -> Mapping[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("could not read inventory: {}".format(exc)) from exc
    if not isinstance(payload, dict):
        raise ValueError("inventory must be a JSON object")
    return payload


def _stored_bytes(root: Path) -> int:
    if not root.exists():
        return 0
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def _json_print(payload: Mapping[str, object]) -> None:
    print(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True))


def _inventory_file(inventory, relative_path: str) -> Mapping[str, object]:
    files = inventory.get("files", [])
    if not isinstance(files, list):
        raise ValueError("inventory.files must be a list")
    for row in files:
        if isinstance(row, dict) and row.get("path") == relative_path:
            return row
    raise ValueError("file is not present in official inventory: {}".format(relative_path))


def _relative(path: Path, project_root: Path) -> str:
    return path.resolve().relative_to(project_root).as_posix()


def _write_csv(path: Path, fieldnames, rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _prepare_cbvd5(record, project_root: Path, args) -> Mapping[str, object]:
    annotation = Path(args.annotation) if args.annotation else record.storage_root / "archives" / "ava_train_v2.1.csv"
    annotation = _inside_project(annotation, project_root, "annotation")
    annotations, parser_exclusions = parse_ava_annotations(annotation)
    video_root = record.storage_root / "raw" / "videos" / "videos"
    candidates = []
    exclusions = [
        {
            "mapping_tier": args.tier,
            "source_video_id": "",
            "source_line_numbers": str(row.line_number),
            "reason": row.reason,
            "raw_row": json.dumps(list(row.raw_row), ensure_ascii=False),
        }
        for row in parser_exclusions
    ]
    hashes = {}
    source_rows = {}
    for annotation_row in annotations:
        mapped = map_cbvd5_labels(annotation_row.source_labels, tier=args.tier)
        if mapped is None:
            exclusions.append(
                {
                    "mapping_tier": args.tier,
                    "source_video_id": annotation_row.video_id,
                    "source_line_numbers": json.dumps(annotation_row.source_line_numbers),
                    "reason": "not_mapped_in_{}_tier".format(args.tier),
                    "raw_row": json.dumps(list(annotation_row.source_labels)),
                }
            )
            continue
        source_video = video_root / "{}.mp4".format(annotation_row.video_id)
        if not source_video.is_file():
            exclusions.append(
                {
                    "mapping_tier": args.tier,
                    "source_video_id": annotation_row.video_id,
                    "source_line_numbers": json.dumps(annotation_row.source_line_numbers),
                    "reason": "source_video_missing",
                    "raw_row": "",
                }
            )
            continue
        source_video = _inside_project(source_video, project_root, "source video")
        source_key = str(source_video)
        if source_key not in hashes:
            hashes[source_key] = sha256_file(source_video)
            source_rows[source_key] = {
                "dataset_id": record.dataset_id,
                "dataset_version": record.version,
                "source_video_id": annotation_row.video_id,
                "path": _relative(source_video, project_root),
                "bytes": source_video.stat().st_size,
                "sha256": hashes[source_key],
            }
        start_second = max(0.0, annotation_row.timestamp - args.clip_seconds / 2.0)
        end_second = start_second + args.clip_seconds
        candidates.append(
            make_clip_record(
                dataset_id=record.dataset_id,
                dataset_version=record.version,
                source_video_id=annotation_row.video_id,
                source_video_path=_relative(source_video, project_root),
                camera_id="unknown",
                start_second=start_second,
                end_second=end_second,
                track_id=annotation_row.entity_id,
                source_labels=annotation_row.source_labels,
                mapped_label=mapped.name,
                mapping_tier=args.tier,
                crop_box=annotation_row.bbox,
                transformations=(
                    "virtual_time_window:{}s".format(args.clip_seconds),
                    "virtual_bbox_crop:annotation_box",
                ),
                output_path=_relative(source_video, project_root),
                output_sha256=hashes[source_key],
            )
        )

    selected = deterministic_class_cap(candidates, args.max_per_class, args.seed)
    selected_ids = {row.sample_id for row in selected}
    for row in candidates:
        if row.sample_id not in selected_ids:
            exclusions.append(
                {
                    "mapping_tier": args.tier,
                    "source_video_id": row.source_video_id,
                    "source_line_numbers": "",
                    "reason": "deterministic_class_cap",
                    "raw_row": row.sample_id,
                }
            )
    assigned = assign_groups(selected, seed=args.seed)
    selected_source_paths = {row.source_video_path for row in assigned}
    selected_source_rows = [
        row for row in source_rows.values() if row["path"] in selected_source_paths
    ]
    manifest_root = record.storage_root / "manifests"
    manifest_root.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_root / "evaluation_clips_{}.csv".format(args.tier)
    write_clip_manifest(manifest_path, assigned)
    _write_csv(
        manifest_root / "source_videos.csv",
        ("dataset_id", "dataset_version", "source_video_id", "path", "bytes", "sha256"),
        sorted(selected_source_rows, key=lambda row: row["source_video_id"]),
    )
    exclusion_path = manifest_root / "excluded_samples.csv"
    existing = []
    if exclusion_path.is_file():
        with exclusion_path.open("r", encoding="utf-8", newline="") as handle:
            existing = [row for row in csv.DictReader(handle) if row.get("mapping_tier") != args.tier]
    exclusion_fields = (
        "mapping_tier",
        "source_video_id",
        "source_line_numbers",
        "reason",
        "raw_row",
    )
    _write_csv(exclusion_path, exclusion_fields, existing + exclusions)
    summary_path = manifest_root / "manifest_summary.json"
    summary = {}
    if summary_path.is_file():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            summary = {}
    counts = {}
    for row in assigned:
        counts[row.mapped_label] = counts.get(row.mapped_label, 0) + 1
    summary[args.tier] = {
        "dataset_id": record.dataset_id,
        "dataset_version": record.version,
        "annotation_path": _relative(annotation, project_root),
        "annotation_sha256": sha256_file(annotation),
        "selection_seed": args.seed,
        "max_per_class": args.max_per_class,
        "clip_seconds": args.clip_seconds,
        "included_samples": len(assigned),
        "included_source_videos": len(selected_source_rows),
        "class_counts": counts,
        "parser_exclusions": len(parser_exclusions),
        "total_exclusions": len(exclusions),
        "split_policy": "external_test_only",
        "clip_materialization": "virtual_window_and_crop",
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "operation": "prepare",
        "dataset_id": record.dataset_id,
        "mapping_tier": args.tier,
        "manifest": _relative(manifest_path, project_root),
        "included_samples": len(assigned),
        "excluded_samples": len(exclusions),
    }


def build_parser() -> argparse.ArgumentParser:
    project_default = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=str(project_default))
    parser.add_argument("--registry")
    parser.add_argument("--inventory")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("inspect", "acquire"):
        child = subparsers.add_parser(command)
        child.add_argument("--dataset", required=True)
        if command == "acquire":
            child.add_argument("--file", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--dataset", required=True)
    prepare.add_argument("--tier", choices=("strict", "extended"), required=True)
    prepare.add_argument("--annotation")
    prepare.add_argument("--max-per-class", type=int, default=250)
    prepare.add_argument("--clip-seconds", type=float, default=4.0)
    prepare.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    project_root = Path(args.project_root).expanduser().resolve()
    registry_path = Path(args.registry).expanduser().resolve() if args.registry else project_root / "data" / "external" / "registry.json"
    inventory_path = Path(args.inventory).expanduser().resolve() if args.inventory else project_root / "data" / "external" / "cbvd5" / "manifests" / "official_inventory_summary.json"
    registry_path = _inside_project(registry_path, project_root, "registry")
    inventory_path = _inside_project(inventory_path, project_root, "inventory")
    registry = load_registry(registry_path, project_root)
    record = registry.require(args.dataset)
    inventory = _load_inventory(inventory_path)

    if args.command == "inspect":
        used = _stored_bytes(record.storage_root)
        _json_print(
            {
                "operation": "inspect_only",
                "dataset_id": record.dataset_id,
                "dataset_version": record.version,
                "license_status": record.license_status,
                "official_url": record.official_url,
                "access_url": record.access_url,
                "storage_root": _relative(record.storage_root, project_root),
                "declared_dataset_bytes": inventory.get("dataset_total_bytes"),
                "download_budget_bytes": record.max_download_bytes,
                "stored_bytes": used,
                "remaining_budget_bytes": record.max_download_bytes - used,
            }
        )
        return 0

    if args.command == "acquire":
        if record.license_status != "verified":
            raise DownloadBlocked(
                "download blocked because dataset license is not verified: {}".format(
                    record.license_status
                )
            )
        source = _inventory_file(inventory, args.file)
        result = acquire_file(
            record,
            RemoteFileSpec(
                relative_path="raw/{}".format(args.file),
                url=source["url"],
                expected_size=source.get("bytes"),
                sha256=source.get("sha256"),
            ),
        )
        operation = {
            "operation": "acquire",
            "dataset_id": record.dataset_id,
            "dataset_version": record.version,
            "source_path": args.file,
            "source_url": source["url"],
            "local_path": _relative(result.path, project_root),
            "bytes": result.size,
            "sha256": result.sha256,
            "reused": result.reused,
        }
        append_operation(record.storage_root / "manifests" / "operations.jsonl", operation)
        _json_print(operation)
        return 0

    if record.dataset_id != "cbvd5":
        raise ValueError("prepare currently supports only cbvd5")
    if args.max_per_class <= 0 or args.clip_seconds <= 0:
        raise ValueError("max_per_class and clip_seconds must be positive")
    result = _prepare_cbvd5(record, project_root, args)
    _json_print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

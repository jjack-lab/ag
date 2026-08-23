from dataclasses import dataclass, replace
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable, Sequence, Tuple


class ClipManifestError(ValueError):
    pass


@dataclass(frozen=True)
class ExternalClipRecord:
    sample_id: str
    source_group_id: str
    dataset_id: str
    dataset_version: str
    source_video_id: str
    source_video_path: str
    camera_id: str
    start_second: float
    end_second: float
    track_id: str
    source_labels: Tuple[str, ...]
    mapped_label: str
    mapping_tier: str
    crop_box: Tuple[float, float, float, float]
    transformations: Tuple[str, ...]
    output_path: str
    output_sha256: str
    split: str = "unassigned"


MANIFEST_FIELDS = (
    "sample_id",
    "source_group_id",
    "dataset_id",
    "dataset_version",
    "source_video_id",
    "source_video_path",
    "camera_id",
    "start_second",
    "end_second",
    "track_id",
    "source_labels",
    "mapped_label",
    "mapping_tier",
    "crop_box",
    "transformations",
    "output_path",
    "output_sha256",
    "split",
)


def _text(value, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ClipManifestError("{} must be non-empty text".format(field))
    return value.strip()


def _digest(*parts) -> str:
    payload = "\x1f".join(str(part) for part in parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _sha256(value: str) -> str:
    normalized = _text(value, "output SHA-256").lower()
    if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
        raise ClipManifestError("output SHA-256 must contain 64 hexadecimal characters")
    return normalized


def make_clip_record(
    *,
    dataset_id: str,
    dataset_version: str,
    source_video_id: str,
    source_video_path: str,
    camera_id: str,
    start_second: float,
    end_second: float,
    track_id: str,
    source_labels: Sequence[str],
    mapped_label: str,
    mapping_tier: str,
    crop_box: Sequence[float],
    transformations: Sequence[str],
    output_path: str,
    output_sha256: str,
    group_block_seconds: int = 60,
) -> ExternalClipRecord:
    dataset_id = _text(dataset_id, "dataset_id")
    dataset_version = _text(dataset_version, "dataset_version")
    source_video_id = _text(source_video_id, "source_video_id")
    source_video_path = _text(source_video_path, "source_video_path")
    camera_id = _text(camera_id, "camera_id")
    track_id = _text(track_id, "track_id")
    mapped_label = _text(mapped_label, "mapped_label")
    output_path = _text(output_path, "output_path")
    if mapping_tier not in {"strict", "extended"}:
        raise ClipManifestError("mapping_tier must be strict or extended")
    if (
        not isinstance(start_second, (int, float))
        or not isinstance(end_second, (int, float))
        or not math.isfinite(float(start_second))
        or not math.isfinite(float(end_second))
        or float(start_second) < 0
        or float(end_second) <= float(start_second)
    ):
        raise ClipManifestError("invalid clip time range")
    if isinstance(group_block_seconds, bool) or not isinstance(group_block_seconds, int) or group_block_seconds <= 0:
        raise ClipManifestError("group_block_seconds must be a positive integer")
    try:
        bbox = tuple(float(value) for value in crop_box)
    except (TypeError, ValueError) as exc:
        raise ClipManifestError("crop_box must contain four normalized numbers") from exc
    if len(bbox) != 4 or not all(math.isfinite(value) for value in bbox):
        raise ClipManifestError("crop_box must contain four normalized numbers")
    x1, y1, x2, y2 = bbox
    if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
        raise ClipManifestError("crop_box must be a valid normalized box")
    labels = tuple(_text(value, "source_label") for value in source_labels)
    if not labels:
        raise ClipManifestError("source_labels must not be empty")
    transforms = tuple(_text(value, "transformation") for value in transformations)
    output_hash = _sha256(output_sha256)
    block = int(float(start_second) // group_block_seconds)
    group_hash = _digest(
        dataset_id, dataset_version, source_video_id, camera_id, block
    )
    sample_hash = _digest(
        dataset_id,
        dataset_version,
        source_video_id,
        camera_id,
        float(start_second),
        float(end_second),
        track_id,
        mapped_label,
        bbox,
    )
    return ExternalClipRecord(
        sample_id="sample_{}".format(sample_hash),
        source_group_id="group_{}".format(group_hash),
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        source_video_id=source_video_id,
        source_video_path=source_video_path,
        camera_id=camera_id,
        start_second=float(start_second),
        end_second=float(end_second),
        track_id=track_id,
        source_labels=labels,
        mapped_label=mapped_label,
        mapping_tier=mapping_tier,
        crop_box=bbox,
        transformations=transforms,
        output_path=output_path,
        output_sha256=output_hash,
    )


def _validate_ratios(ratios) -> Tuple[float, float, float]:
    if len(ratios) != 3:
        raise ClipManifestError("ratios must contain train, val, and test")
    values = tuple(float(value) for value in ratios)
    if any(not math.isfinite(value) or value < 0 for value in values) or not math.isclose(
        sum(values), 1.0, rel_tol=0, abs_tol=1e-9
    ):
        raise ClipManifestError("ratios must be non-negative and sum to 1")
    return values


def assign_groups(
    records: Iterable[ExternalClipRecord],
    seed: int,
    ratios=(0.0, 0.0, 1.0),
) -> Tuple[ExternalClipRecord, ...]:
    train_ratio, val_ratio, _ = _validate_ratios(ratios)
    assigned = {}
    result = []
    for record in records:
        if record.source_group_id not in assigned:
            rank = int(
                hashlib.sha256(
                    "{}:{}".format(seed, record.source_group_id).encode("utf-8")
                ).hexdigest(),
                16,
            ) / float(2**256)
            split = "train" if rank < train_ratio else "val" if rank < train_ratio + val_ratio else "test"
            assigned[record.source_group_id] = split
        result.append(replace(record, split=assigned[record.source_group_id]))
    output = tuple(result)
    validate_no_group_leakage(output)
    return output


def validate_no_group_leakage(records: Iterable[ExternalClipRecord]) -> None:
    owners = {}
    sample_ids = set()
    for record in records:
        if record.sample_id in sample_ids:
            raise ClipManifestError("duplicate sample_id: {}".format(record.sample_id))
        sample_ids.add(record.sample_id)
        previous = owners.setdefault(record.source_group_id, record.split)
        if previous != record.split:
            raise ClipManifestError(
                "group leakage: {} occurs in {} and {}".format(
                    record.source_group_id, previous, record.split
                )
            )


def deterministic_class_cap(
    records: Iterable[ExternalClipRecord], max_per_class: int, seed: int
) -> Tuple[ExternalClipRecord, ...]:
    if isinstance(max_per_class, bool) or not isinstance(max_per_class, int) or max_per_class <= 0:
        raise ClipManifestError("max_per_class must be a positive integer")
    grouped = {}
    for record in records:
        grouped.setdefault(record.mapped_label, []).append(record)
    selected = []
    for label in sorted(grouped):
        ranked = sorted(
            grouped[label],
            key=lambda row: (
                _digest(seed, row.sample_id),
                row.sample_id,
            ),
        )
        selected.extend(ranked[:max_per_class])
    return tuple(sorted(selected, key=lambda row: (row.mapped_label, row.sample_id)))


def write_clip_manifest(path: Path, records: Iterable[ExternalClipRecord]) -> Path:
    rows = tuple(records)
    validate_no_group_leakage(rows)
    if any(record.split not in {"train", "val", "test"} for record in rows):
        raise ClipManifestError("all manifest records must have an assigned split")
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
            writer.writeheader()
            for record in rows:
                writer.writerow(
                    {
                        "sample_id": record.sample_id,
                        "source_group_id": record.source_group_id,
                        "dataset_id": record.dataset_id,
                        "dataset_version": record.dataset_version,
                        "source_video_id": record.source_video_id,
                        "source_video_path": record.source_video_path,
                        "camera_id": record.camera_id,
                        "start_second": record.start_second,
                        "end_second": record.end_second,
                        "track_id": record.track_id,
                        "source_labels": json.dumps(list(record.source_labels)),
                        "mapped_label": record.mapped_label,
                        "mapping_tier": record.mapping_tier,
                        "crop_box": json.dumps(list(record.crop_box)),
                        "transformations": json.dumps(list(record.transformations)),
                        "output_path": record.output_path,
                        "output_sha256": record.output_sha256,
                        "split": record.split,
                    }
                )
        temporary.replace(output)
        return output
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

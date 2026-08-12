from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from cattle_health_app.behavior.labels import (
    UnknownBehaviorLabel,
    canonical_label,
)


REQUIRED_FIELDS = (
    "segment_id",
    "source_id",
    "video_path",
    "trajectory_path",
    "dataset",
    "license",
    "group_id",
    "cattle_id",
    "track_id",
    "start_second",
    "end_second",
    "label",
)


class ManifestValidationError(ValueError):
    pass


@dataclass(frozen=True)
class SourceSegment:
    segment_id: str
    source_id: str
    video_path: Path
    trajectory_path: Path
    dataset: str
    license: str
    group_id: str
    cattle_id: str
    reviewed_track_id: int | None
    start_second: float
    end_second: float
    label: str


def _required(row: dict, field: str, row_number: int) -> str:
    value = (row.get(field) or "").strip()
    if not value:
        raise ManifestValidationError(
            f"Row {row_number}: {field} must not be blank"
        )
    return value


def _path(base: Path, value: str) -> Path:
    candidate = Path(value).expanduser()
    return candidate if candidate.is_absolute() else (base / candidate)


def _track_id(value: str, row_number: int) -> int | None:
    cleaned = (value or "").strip()
    if not cleaned:
        return None
    try:
        parsed = int(cleaned)
    except ValueError as error:
        raise ManifestValidationError(
            f"Row {row_number}: track_id must be an integer or blank"
        ) from error
    if parsed < 0:
        raise ManifestValidationError(
            f"Row {row_number}: track_id must be non-negative"
        )
    return parsed


def load_source_segments(manifest_path: str | Path) -> list[SourceSegment]:
    path = Path(manifest_path).resolve()
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        fieldnames = reader.fieldnames or []
        missing = [field for field in REQUIRED_FIELDS if field not in fieldnames]
        if missing:
            raise ManifestValidationError(
                f"Missing manifest fields: {', '.join(missing)}"
            )
        rows = list(reader)

    segments = []
    seen_segment_ids = set()
    for row_number, row in enumerate(rows, start=2):
        segment_id = _required(row, "segment_id", row_number)
        if segment_id in seen_segment_ids:
            raise ManifestValidationError(
                f"Row {row_number}: duplicate segment_id {segment_id!r}"
            )
        seen_segment_ids.add(segment_id)
        try:
            start_second = float(_required(row, "start_second", row_number))
            end_second = float(_required(row, "end_second", row_number))
        except ValueError as error:
            raise ManifestValidationError(
                f"Row {row_number}: start_second and end_second must be numeric"
            ) from error
        if start_second < 0 or end_second <= start_second:
            raise ManifestValidationError(
                f"Row {row_number}: end_second must be greater than start_second"
            )
        try:
            label = canonical_label(_required(row, "label", row_number))
        except UnknownBehaviorLabel as error:
            raise ManifestValidationError(
                f"Row {row_number}: {error}"
            ) from error
        segments.append(
            SourceSegment(
                segment_id=segment_id,
                source_id=_required(row, "source_id", row_number),
                video_path=_path(
                    path.parent, _required(row, "video_path", row_number)
                ),
                trajectory_path=_path(
                    path.parent,
                    _required(row, "trajectory_path", row_number),
                ),
                dataset=_required(row, "dataset", row_number),
                license=_required(row, "license", row_number),
                group_id=_required(row, "group_id", row_number),
                cattle_id=_required(row, "cattle_id", row_number),
                reviewed_track_id=_track_id(row.get("track_id", ""), row_number),
                start_second=start_second,
                end_second=end_second,
                label=label,
            )
        )
    if not segments:
        raise ManifestValidationError("Manifest contains no source segments")
    return segments

import csv
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple


ACTION_LABELS = {
    1: "standing",
    2: "lying",
    3: "foraging",
    4: "drinking",
    5: "rumination",
}
LABEL_ORDER = {name: action_id for action_id, name in ACTION_LABELS.items()}


@dataclass(frozen=True)
class SourceAnnotation:
    video_id: str
    timestamp: float
    bbox: Tuple[float, float, float, float]
    entity_id: str
    source_labels: Tuple[str, ...]
    source_line_numbers: Tuple[int, ...]


@dataclass(frozen=True)
class MappedLabel:
    name: str
    mapping_tier: str
    source_labels: Tuple[str, ...]


@dataclass(frozen=True)
class ExcludedAnnotation:
    line_number: int
    reason: str
    raw_row: Tuple[str, ...]


def _ordered_labels(labels: Iterable[str]) -> Tuple[str, ...]:
    return tuple(sorted(set(labels), key=lambda value: LABEL_ORDER.get(value, 999)))


def map_cbvd5_labels(
    source_labels: Iterable[str], tier: str = "strict"
) -> Optional[MappedLabel]:
    if tier not in {"strict", "extended"}:
        raise ValueError("tier must be strict or extended")
    labels = _ordered_labels(source_labels)
    values = set(labels)
    if not values or not values.issubset(set(LABEL_ORDER)):
        return None
    if {"standing", "lying"}.issubset(values):
        return None
    states = values.intersection({"foraging", "drinking", "rumination"})
    if len(states) > 1:
        return None
    if "foraging" in states:
        return MappedLabel("grazing", tier, labels)
    if "drinking" in states:
        return MappedLabel("drinking", tier, labels)
    if "rumination" in states:
        if "standing" in values:
            return MappedLabel("ruminating-standing", tier, labels)
        if "lying" in values:
            return MappedLabel("ruminating-lying", tier, labels)
        return None
    if tier == "extended" and values == {"standing"}:
        return MappedLabel("resting-standing", tier, labels)
    if tier == "extended" and values == {"lying"}:
        return MappedLabel("resting-lying", tier, labels)
    return None


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("not finite")
    return number


def parse_ava_annotations(
    path: Path,
) -> Tuple[Tuple[SourceAnnotation, ...], Tuple[ExcludedAnnotation, ...]]:
    groups: Dict[Tuple[object, ...], Dict[str, object]] = {}
    exclusions = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        for line_number, row in enumerate(csv.reader(handle), start=1):
            raw_row = tuple(row)
            if len(row) != 8:
                exclusions.append(
                    ExcludedAnnotation(line_number, "expected_8_columns", raw_row)
                )
                continue
            video_id, timestamp_raw, x1_raw, y1_raw, x2_raw, y2_raw, action_raw, entity_id = row
            if not video_id.strip() or not entity_id.strip():
                exclusions.append(
                    ExcludedAnnotation(line_number, "blank_identifier", raw_row)
                )
                continue
            try:
                timestamp = _finite_float(timestamp_raw)
                bbox = tuple(
                    _finite_float(value)
                    for value in (x1_raw, y1_raw, x2_raw, y2_raw)
                )
            except ValueError:
                exclusions.append(
                    ExcludedAnnotation(line_number, "invalid_numeric_value", raw_row)
                )
                continue
            if timestamp < 0:
                exclusions.append(
                    ExcludedAnnotation(line_number, "invalid_timestamp", raw_row)
                )
                continue
            x1, y1, x2, y2 = bbox
            if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
                exclusions.append(ExcludedAnnotation(line_number, "invalid_bbox", raw_row))
                continue
            try:
                action_id = int(action_raw)
                if str(action_id) != action_raw.strip() or action_id not in ACTION_LABELS:
                    raise ValueError("invalid action")
            except ValueError:
                exclusions.append(
                    ExcludedAnnotation(line_number, "invalid_action_id", raw_row)
                )
                continue
            key = (video_id.strip(), timestamp, bbox, entity_id.strip())
            group = groups.setdefault(
                key,
                {
                    "labels": set(),
                    "lines": [],
                    "raw": raw_row,
                },
            )
            group["labels"].add(ACTION_LABELS[action_id])
            group["lines"].append(line_number)

    annotations = []
    for key, group in groups.items():
        video_id, timestamp, bbox, entity_id = key
        labels = _ordered_labels(group["labels"])
        if {"standing", "lying"}.issubset(set(labels)):
            exclusions.append(
                ExcludedAnnotation(
                    group["lines"][0], "conflicting_posture_labels", group["raw"]
                )
            )
            continue
        annotations.append(
            SourceAnnotation(
                video_id=video_id,
                timestamp=timestamp,
                bbox=bbox,
                entity_id=entity_id,
                source_labels=labels,
                source_line_numbers=tuple(group["lines"]),
            )
        )
    return tuple(annotations), tuple(exclusions)

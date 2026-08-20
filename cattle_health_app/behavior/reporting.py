"""Versioned behavior timeline, aggregation, and JSON artifacts."""

from __future__ import annotations

import csv
import json
import math
import os
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

TIMELINE_FIELDS = (
    "frame_index", "time_seconds", "track_id", "label_id", "label",
    "display_name", "confidence", "health_eligible", "model_version",
)
SUMMARY_FIELDS = (
    "track_id", "label_id", "label", "display_name", "duration_seconds",
    "percentage", "mean_confidence", "health_eligible", "model_version",
    "behavior_name", "behavior_display_name", "eligible_ratio",
    "uncertain_duration_seconds",
)
UNCERTAIN_IDS = frozenset((1, 10, 11))
REPORT_SCHEMA_VERSION = 2


@dataclass(frozen=True)
class BehaviorObservation:
    frame_index: int
    time_seconds: float
    track_id: int
    label_id: int
    label: str
    display_name: str
    confidence: float
    health_eligible: bool
    model_version: str

    def __post_init__(self) -> None:
        if isinstance(self.frame_index, bool) or not isinstance(self.frame_index, int) or self.frame_index < 0:
            raise ValueError("frame_index must be a nonnegative integer")
        if isinstance(self.track_id, bool) or not isinstance(self.track_id, int) or self.track_id < 0:
            raise ValueError("track_id must be a nonnegative integer")
        if not math.isfinite(float(self.time_seconds)) or self.time_seconds < 0:
            raise ValueError("time_seconds must be finite and nonnegative")
        if not math.isfinite(float(self.confidence)) or not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be finite and in [0, 1]")


def _normalized(observation, threshold):
    uncertain = (
        observation.label_id in UNCERTAIN_IDS
        or not observation.health_eligible
        or observation.confidence < threshold
    )
    if not uncertain:
        return observation
    return BehaviorObservation(
        observation.frame_index, observation.time_seconds, observation.track_id,
        1, "none", "无法确定", observation.confidence, False,
        observation.model_version,
    )


def build_behavior_summary(
    observations: Iterable[BehaviorObservation],
    fps: float,
    confidence_threshold: float = 0.45,
) -> list:
    if not math.isfinite(float(fps)) or fps <= 0:
        raise ValueError("fps must be finite and positive")
    if not math.isfinite(float(confidence_threshold)) or not 0 <= confidence_threshold <= 1:
        raise ValueError("confidence_threshold must be in [0, 1]")
    normalized = []
    for value in observations:
        if not isinstance(value, BehaviorObservation):
            raise TypeError("observations must contain BehaviorObservation values")
        normalized.append(_normalized(value, confidence_threshold))

    by_track = defaultdict(list)
    for position, item in enumerate(normalized):
        by_track[item.track_id].append((position, item))
    durations = [0.0] * len(normalized)
    for items in by_track.values():
        items.sort(key=lambda value: (value[1].time_seconds, value[1].frame_index))
        last_positive_interval = 0.0
        for index, (position, item) in enumerate(items[:-1]):
            interval = items[index + 1][1].time_seconds - item.time_seconds
            duration = interval if interval > 0 else 0.0
            durations[position] = duration
            if duration > 0:
                last_positive_interval = duration
        durations[items[-1][0]] = last_positive_interval if len(items) > 1 else 0.0

    grouped = defaultdict(lambda: {"confidences": [], "duration": 0.0})
    totals = defaultdict(float)
    for position, item in enumerate(normalized):
        key = (
            item.track_id, item.label_id, item.label, item.display_name,
            item.health_eligible, item.model_version,
        )
        duration = durations[position]
        grouped[key]["confidences"].append(item.confidence)
        grouped[key]["duration"] += duration
        totals[item.track_id] += duration
    rows = []
    for key in sorted(grouped):
        track_id, label_id, label, display_name, eligible, version = key
        confidences = grouped[key]["confidences"]
        count = len(confidences)
        duration = grouped[key]["duration"]
        rows.append(
            {
                "track_id": track_id,
                "label_id": label_id,
                "label": label,
                "display_name": display_name,
                "duration_seconds": round(duration, 6),
                "percentage": (
                    round(100.0 * duration / totals[track_id], 6)
                    if totals[track_id] else 0.0
                ),
                "mean_confidence": round(sum(confidences) / count, 6),
                "health_eligible": eligible,
                "model_version": version,
            }
        )
    return rows


def _atomic_csv(path, rows, fields):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8-sig", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
            target.flush()
            os.fsync(target.fileno())
        os.replace(str(temporary), str(path))
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def write_behavior_timeline(path: Path, observations: Iterable[BehaviorObservation]) -> None:
    _atomic_csv(path, [asdict(item) for item in observations], TIMELINE_FIELDS)


def write_behavior_summary(path: Path, rows: Sequence[Mapping]) -> None:
    eligible_totals = defaultdict(float)
    uncertain_totals = defaultdict(float)
    for row in rows:
        target = eligible_totals if row["health_eligible"] else uncertain_totals
        target[int(row["track_id"])] += float(row["duration_seconds"])
    exported = []
    for row in rows:
        track_id = int(row["track_id"])
        eligible_total = eligible_totals[track_id]
        value = dict(row)
        value.update({
            "behavior_name": row["label"],
            "behavior_display_name": row["display_name"],
            "eligible_ratio": round(float(row["duration_seconds"]) / eligible_total, 6)
            if row["health_eligible"] and eligible_total else 0.0,
            "uncertain_duration_seconds": round(uncertain_totals[track_id], 6),
        })
        exported.append(value)
    _atomic_csv(path, exported, SUMMARY_FIELDS)


def write_behavior_report(
    path: Path,
    observations: Iterable[BehaviorObservation],
    summary: Sequence[Mapping],
    status: str,
    model_version: Optional[str],
    fps: float,
    error: Optional[str] = None,
    decode_error_count: int = 0,
) -> dict:
    observations = list(observations)
    by_track = defaultdict(lambda: [0.0, 0.0])
    eligible_by_track = defaultdict(lambda: defaultdict(float))
    for row in summary:
        track_id = int(row["track_id"])
        duration = float(row["duration_seconds"])
        by_track[track_id][0 if row["health_eligible"] else 1] += duration
        if row["health_eligible"]:
            eligible_by_track[track_id][str(row["label"])] += duration
    health = {}
    for track_id, (eligible, uncertain) in sorted(by_track.items()):
        percentages = (
            {
                label: round(100.0 * duration / eligible, 6)
                for label, duration in sorted(eligible_by_track[track_id].items())
            }
            if eligible
            else {}
        )
        health[str(track_id)] = {
            "eligible_duration_seconds": round(eligible, 6),
            "uncertain_duration_seconds": round(uncertain, 6),
            "eligible_behavior_percentages": percentages,
            "denominator": "eligible_behavior_duration_only",
        }
    payload = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "summary_fields": list(SUMMARY_FIELDS),
        "behavior_model_status": status,
        "behavior_model_version": model_version,
        "fps": float(fps),
        "decode_error_count": int(decode_error_count),
        "observation_count": len(observations),
        "summary": list(summary),
        "health_statistics": health,
        "error": error,
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as target:
            json.dump(payload, target, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
            target.write("\n")
            target.flush()
            os.fsync(target.fileno())
        os.replace(str(temporary), str(path))
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return payload

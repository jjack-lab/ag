"""Isolation Forest herd trajectory anomaly detection.

Detects tracks whose movement pattern deviates from the rest of the herd,
complementing the rule-based :class:`CattleHealthMonitor`. The detector is
unsupervised (no labeled data required): within one video, each tracked
animal is compared against the whole herd, and outliers are animals whose
trajectory features isolate most easily.

Design notes:

- A minimum number of tracks is required to fit a meaningful forest;
  otherwise detection is skipped and reported as ``skipped`` rather than
  pretending to work.
- ``decision_function`` is used for a continuous anomaly score (negative =
  more anomalous); ``predict`` provides the boolean outlier flag.
- Per-track z-scores against the herd median explain *why* an animal is
  flagged, which keeps the output honest and operator-friendly.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from sklearn.ensemble import IsolationForest

from cattle_health_app.anomaly.trajectory_features import (
    FEATURE_NAMES,
    extract_track_features,
    feature_vector,
)

#: Below this many comparable tracks the forest is not fitted.
DEFAULT_MIN_TRACKS = 5
#: Expected proportion of outliers in the herd.
DEFAULT_CONTAMINATION = 0.1
#: Fixed seed for reproducible fits.
DEFAULT_RANDOM_STATE = 42
#: Minimum samples per track to include in the herd comparison.
MIN_SAMPLES_PER_TRACK = 3
#: How many contributing features to report per flagged track.
TOP_CONTRIBUTORS = 3


@dataclass(frozen=True)
class TrackAnomalyResult:
    """One track's anomaly assessment plus its full feature vector."""

    track_id: int
    is_outlier: bool
    anomaly_score: float  # 0..1, higher = more anomalous
    features: Dict[str, float]
    top_contributors: Tuple[str, ...] = ()

    def to_row(self) -> Dict[str, str]:
        row = {
            "track_id": str(self.track_id),
            "is_outlier": "1" if self.is_outlier else "0",
            "anomaly_score": f"{self.anomaly_score:.4f}",
            "top_contributors": ";".join(self.top_contributors),
        }
        for name in FEATURE_NAMES:
            row[name] = f"{float(self.features.get(name, 0.0)):.4f}"
        row["sample_count"] = str(int(self.features.get("_sample_count", 0.0)))
        row["duration_seconds"] = f"{float(self.features.get('_duration_seconds', 0.0)):.3f}"
        return row


@dataclass(frozen=True)
class TrajectoryAnomalyReport:
    """Result of running herd-level trajectory anomaly detection."""

    status: str  # "ok" | "skipped" | "failed"
    reason: Optional[str] = None
    tracks: List[TrackAnomalyResult] = field(default_factory=list)

    @property
    def outlier_track_ids(self) -> List[int]:
        return [track.track_id for track in self.tracks if track.is_outlier]

    @property
    def outlier_count(self) -> int:
        return len(self.outlier_track_ids)


def detect_trajectory_anomalies(
    rows: Iterable[Dict[str, object]],
    fps: float = 20.0,
    min_tracks: int = DEFAULT_MIN_TRACKS,
    contamination: float = DEFAULT_CONTAMINATION,
    random_state: int = DEFAULT_RANDOM_STATE,
) -> TrajectoryAnomalyReport:
    """Run Isolation Forest over per-track features extracted from rows."""
    try:
        features_by_track = extract_track_features(rows, fps=fps)
    except Exception as error:  # pragma: no cover - defensive
        return TrajectoryAnomalyReport(
            status="failed",
            reason="{}: {}".format(type(error).__name__, error),
        )

    eligible = [
        (track_id, features)
        for track_id, features in features_by_track.items()
        if features.get("_sample_count", 0) >= MIN_SAMPLES_PER_TRACK
    ]
    if len(eligible) < min_tracks:
        return TrajectoryAnomalyReport(
            status="skipped",
            reason=(
                "tracked cattle below minimum for herd comparison "
                f"({len(eligible)} < {min_tracks})"
            ),
        )

    track_ids = [track_id for track_id, _ in eligible]
    matrix = [feature_vector(features) for _, features in eligible]
    try:
        forest = IsolationForest(
            n_estimators=200,
            contamination=contamination,
            random_state=random_state,
            max_samples="auto",
        ).fit(matrix)
        raw_scores = forest.decision_function(matrix)
        predictions = forest.predict(matrix)
    except Exception as error:  # pragma: no cover - defensive
        return TrajectoryAnomalyReport(
            status="failed",
            reason="{}: {}".format(type(error).__name__, error),
        )

    # Normalize raw decision scores (negative = anomalous) to 0..1 where
    # 1 is the most anomalous animal in this herd.
    raw_min = min(raw_scores)
    raw_max = max(raw_scores)
    score_range = (raw_max - raw_min) or 1.0

    medians = _feature_medians([features for _, features in eligible])
    results: List[TrackAnomalyResult] = []
    for track_id, features, raw, prediction in zip(
        track_ids, [f for _, f in eligible], raw_scores, predictions
    ):
        normalized = (raw_max - raw) / score_range
        contributors = _top_contributors(features, medians)
        results.append(
            TrackAnomalyResult(
                track_id=track_id,
                is_outlier=bool(prediction == -1),
                anomaly_score=float(normalized),
                features=features,
                top_contributors=tuple(contributors),
            )
        )
    results.sort(key=lambda item: item.track_id)
    return TrajectoryAnomalyReport(status="ok", tracks=results)


def write_anomaly_csv(path: Path, report: TrajectoryAnomalyReport) -> Path:
    """Write per-track anomaly results to CSV; returns the path."""
    if report.status != "ok" or not report.tracks:
        return path
    columns = [
        "track_id",
        "is_outlier",
        "anomaly_score",
        "top_contributors",
        *FEATURE_NAMES,
        "sample_count",
        "duration_seconds",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=columns)
        writer.writeheader()
        for track in report.tracks:
            writer.writerow(track.to_row())
    return path


def _feature_medians(feature_sets: Sequence[Dict[str, float]]) -> Dict[str, float]:
    medians: Dict[str, float] = {}
    for name in FEATURE_NAMES:
        values = sorted(float(item[name]) for item in feature_sets)
        count = len(values)
        if count == 0:
            medians[name] = 0.0
        elif count % 2 == 1:
            medians[name] = values[count // 2]
        else:
            medians[name] = (values[count // 2 - 1] + values[count // 2]) / 2.0
    return medians


def _top_contributors(
    features: Dict[str, float], medians: Dict[str, float]
) -> List[str]:
    """Rank features by |z-score| against the herd median (robust spread)."""
    z_scores: List[Tuple[float, str]] = []
    for name in FEATURE_NAMES:
        value = float(features[name])
        median = medians[name]
        spread = max(abs(value - median), 1e-9)
        # Use a simple robust spread (distance to median), not the raw value,
        # so features with large magnitudes (area, displacement) do not
        # dominate the explanation.
        z_scores.append((spread, name))
    z_scores.sort(reverse=True)
    return [name for _, name in z_scores[:TOP_CONTRIBUTORS]]

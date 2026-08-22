"""Per-track trajectory feature engineering for herd anomaly detection.

Trajectory rows are the same records written to ``*_tracks.csv`` by the
tracking pipeline::

    frame_index, time_seconds, track_id, class_id, confidence,
    center_x, center_y, width, height

Features are computed per track (and where meaningful relative to the whole
herd, e.g. distance to the herd centroid or to the nearest neighbor). The
feature set is intentionally small and interpretable so the Isolation Forest
output can be explained per track.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Dict, Iterable, List, Sequence, Tuple

Point = Tuple[float, float]

#: Feature names in the fixed order used by the detector matrix.
FEATURE_NAMES: Tuple[str, ...] = (
    "mean_speed_px_s",
    "std_speed_px_s",
    "max_speed_px_s",
    "speed_cv",
    "mean_accel_px_s2",
    "std_accel_px_s2",
    "activity_radius_px",
    "total_displacement_px",
    "meander_ratio",
    "mean_distance_to_herd_px",
    "min_distance_to_herd_px",
    "mean_nearest_neighbor_px",
    "aspect_mean",
    "aspect_std",
    "area_mean_px2",
)


def _distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _stats(values: Sequence[float]) -> Tuple[float, float]:
    """Return (mean, std) with a safe zero fallback for empty sequences."""
    if not values:
        return 0.0, 0.0
    count = len(values)
    mean = sum(values) / count
    variance = sum((value - mean) ** 2 for value in values) / count
    return mean, math.sqrt(variance)


def extract_track_features(
    rows: Iterable[Dict[str, object]], fps: float = 20.0
) -> Dict[int, Dict[str, float]]:
    """Group trajectory rows by track and compute one feature vector each.

    Returns a mapping ``{track_id: {feature_name: value}}``.
    """
    by_track: Dict[int, List[Dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_track[int(row["track_id"])].append(row)

    for track_rows in by_track.values():
        track_rows.sort(key=lambda row: int(row["frame_index"]))

    # Per-frame herd geometry: entries = frame -> [(track_id, x, y)]
    frame_entries: Dict[int, List[Tuple[int, float, float]]] = defaultdict(list)
    for track_id, track_rows in by_track.items():
        for row in track_rows:
            frame_entries[int(row["frame_index"])].append(
                (
                    track_id,
                    float(row["center_x"]),
                    float(row["center_y"]),
                )
            )

    herd_centroid: Dict[int, Point] = {}
    nearest_by_track: Dict[int, Dict[int, float]] = defaultdict(dict)
    for frame, entries in frame_entries.items():
        centroid_x = sum(entry[1] for entry in entries) / len(entries)
        centroid_y = sum(entry[2] for entry in entries) / len(entries)
        herd_centroid[frame] = (centroid_x, centroid_y)
        if len(entries) < 2:
            for track_id, _, _ in entries:
                nearest_by_track[track_id][frame] = None
            continue
        for track_id, x, y in entries:
            distances = [
                math.hypot(x - other_x, y - other_y)
                for other_id, other_x, other_y in entries
                if other_id != track_id
            ]
            nearest_by_track[track_id][frame] = min(distances)

    features: Dict[int, Dict[str, float]] = {}
    for track_id, track_rows in by_track.items():
        features[track_id] = _track_features(
            track_id, track_rows, herd_centroid, nearest_by_track[track_id], fps
        )
    return features


def _track_features(
    track_id: int,
    track_rows: List[Dict[str, object]],
    herd_centroid: Dict[int, Point],
    nearest_by_frame: Dict[int, float],
    fps: float,
) -> Dict[str, float]:
    centers = [
        (float(row["center_x"]), float(row["center_y"])) for row in track_rows
    ]
    frames = [int(row["frame_index"]) for row in track_rows]
    widths = [float(row["width"]) for row in track_rows]
    heights = [float(row["height"]) for row in track_rows]

    # Speeds between consecutive detections (px/s).
    speeds: List[float] = []
    for index in range(1, len(track_rows)):
        frame_delta = max(frames[index] - frames[index - 1], 1)
        speeds.append(_distance(centers[index - 1], centers[index]) / frame_delta * fps)

    # Accelerations between consecutive speed samples (px/s^2).
    accels: List[float] = []
    for index in range(1, len(speeds)):
        frame_delta = max(frames[index + 1] - frames[index], 1)
        accels.append((speeds[index] - speeds[index - 1]) / frame_delta * fps)

    speed_mean, speed_std = _stats(speeds)
    accel_mean, accel_std = _stats(accels)

    # Activity radius: spread of center positions around the track mean.
    center_mean_x = sum(point[0] for point in centers) / len(centers)
    center_mean_y = sum(point[1] for point in centers) / len(centers)
    variance_x = sum((point[0] - center_mean_x) ** 2 for point in centers) / len(centers)
    variance_y = sum((point[1] - center_mean_y) ** 2 for point in centers) / len(centers)
    activity_radius = math.sqrt(variance_x + variance_y)

    total_displacement = sum(
        _distance(centers[index - 1], centers[index])
        for index in range(1, len(centers))
    )
    net_displacement = (
        _distance(centers[0], centers[-1]) if len(centers) > 1 else 0.0
    )
    meander_ratio = total_displacement / max(net_displacement, 1e-6)

    # Distances to the herd centroid on frames where the track is visible.
    herd_distances: List[float] = []
    for frame_index, center in zip(frames, centers):
        centroid = herd_centroid.get(frame_index)
        if centroid is not None:
            herd_distances.append(_distance(center, centroid))
    herd_mean, _ = _stats(herd_distances)
    herd_min = min(herd_distances) if herd_distances else 0.0

    # Distance to the nearest herd mate, averaged over visible frames.
    neighbor_distances = [
        value for value in nearest_by_frame.values() if value is not None
    ]
    neighbor_mean, _ = _stats(neighbor_distances)

    aspect_ratios = [
        width / max(height, 1.0) for width, height in zip(widths, heights)
    ]
    aspect_mean, aspect_std = _stats(aspect_ratios)
    area_mean, _ = _stats([w * h for w, h in zip(widths, heights)])

    return {
        "mean_speed_px_s": speed_mean,
        "std_speed_px_s": speed_std,
        "max_speed_px_s": max(speeds) if speeds else 0.0,
        "speed_cv": (speed_std / speed_mean) if speed_mean > 0 else 0.0,
        "mean_accel_px_s2": accel_mean,
        "std_accel_px_s2": accel_std,
        "activity_radius_px": activity_radius,
        "total_displacement_px": total_displacement,
        "meander_ratio": meander_ratio,
        "mean_distance_to_herd_px": herd_mean,
        "min_distance_to_herd_px": herd_min,
        "mean_nearest_neighbor_px": neighbor_mean,
        "aspect_mean": aspect_mean,
        "aspect_std": aspect_std,
        "area_mean_px2": area_mean,
        "_sample_count": float(len(track_rows)),
        "_duration_seconds": (
            float(frames[-1] - frames[0]) / max(fps, 0.001)
            if len(frames) > 1
            else 0.0
        ),
    }


def feature_vector(features: Dict[str, float]) -> List[float]:
    """Extract the fixed-order numeric vector used by the detector."""
    return [float(features[name]) for name in FEATURE_NAMES]

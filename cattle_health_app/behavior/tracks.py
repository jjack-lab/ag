from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path


class TrackSelectionError(ValueError):
    pass


@dataclass(frozen=True)
class TrackObservation:
    frame_index: int
    time_seconds: float
    track_id: int
    confidence: float
    center_x: float
    center_y: float
    width: float
    height: float
    interpolated: bool = False


def load_track_observations(path: str | Path) -> list[TrackObservation]:
    observations = {}
    with Path(path).open("r", encoding="utf-8-sig", newline="") as source:
        for row_number, row in enumerate(csv.DictReader(source), start=2):
            try:
                observation = TrackObservation(
                    frame_index=int(row["frame_index"]),
                    time_seconds=float(row["time_seconds"]),
                    track_id=int(row["track_id"]),
                    confidence=float(row["confidence"]),
                    center_x=float(row["center_x"]),
                    center_y=float(row["center_y"]),
                    width=float(row["width"]),
                    height=float(row["height"]),
                )
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(
                    f"Invalid trajectory row {row_number} in {path}"
                ) from error
            key = (observation.track_id, observation.frame_index)
            current = observations.get(key)
            if current is None or observation.confidence > current.confidence:
                observations[key] = observation
    return sorted(
        observations.values(),
        key=lambda item: (item.frame_index, item.track_id),
    )


def select_track_id(
    observations: list[TrackObservation],
    start_second: float,
    end_second: float,
    reviewed_track_id: int | None,
) -> tuple[int, str]:
    window = [
        item
        for item in observations
        if start_second <= item.time_seconds < end_second
    ]
    counts = Counter(item.track_id for item in window)
    if reviewed_track_id is not None:
        if reviewed_track_id not in counts:
            raise TrackSelectionError(
                f"Missing reviewed track {reviewed_track_id} in segment"
            )
        return reviewed_track_id, "reviewed"
    if not counts:
        raise TrackSelectionError("No tracked cattle in segment")
    selected = min(counts, key=lambda track_id: (-counts[track_id], track_id))
    return selected, "automatic_coverage"


def _interpolate(
    left: TrackObservation,
    right: TrackObservation,
    frame: int,
) -> TrackObservation:
    ratio = (frame - left.frame_index) / (
        right.frame_index - left.frame_index
    )

    def blend(name):
        return getattr(left, name) + (
            getattr(right, name) - getattr(left, name)
        ) * ratio

    return replace(
        left,
        frame_index=frame,
        time_seconds=blend("time_seconds"),
        confidence=min(left.confidence, right.confidence),
        center_x=blend("center_x"),
        center_y=blend("center_y"),
        width=blend("width"),
        height=blend("height"),
        interpolated=True,
    )


def interpolate_track(
    observations: list[TrackObservation],
    track_id: int,
    start_frame: int,
    end_frame: int,
    max_gap: int,
) -> dict[int, TrackObservation]:
    selected = sorted(
        (
            item
            for item in observations
            if item.track_id == track_id
            and start_frame <= item.frame_index < end_frame
        ),
        key=lambda item: item.frame_index,
    )
    result = {item.frame_index: item for item in selected}
    for left, right in zip(selected, selected[1:]):
        missing = right.frame_index - left.frame_index - 1
        if 0 < missing <= max_gap:
            for frame in range(left.frame_index + 1, right.frame_index):
                result[frame] = _interpolate(left, right, frame)
    return result

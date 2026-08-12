import csv

import pytest

from cattle_health_app.behavior.tracks import (
    TrackSelectionError,
    interpolate_track,
    load_track_observations,
    select_track_id,
)


FIELDS = [
    "frame_index",
    "time_seconds",
    "track_id",
    "class_id",
    "confidence",
    "center_x",
    "center_y",
    "width",
    "height",
]


def write_tracks(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def row(frame, track_id, confidence=0.9, center_x=50):
    return {
        "frame_index": frame,
        "time_seconds": frame / 10,
        "track_id": track_id,
        "class_id": 1,
        "confidence": confidence,
        "center_x": center_x,
        "center_y": 40,
        "width": 20,
        "height": 16,
    }


def test_selects_reviewed_track_or_highest_coverage(tmp_path):
    path = tmp_path / "tracks.csv"
    write_tracks(
        path,
        [row(frame, 7) for frame in range(8)]
        + [row(frame, 3) for frame in range(5)],
    )
    observations = load_track_observations(path)

    assert select_track_id(observations, 0.0, 1.0, reviewed_track_id=3) == (
        3,
        "reviewed",
    )
    assert select_track_id(observations, 0.0, 1.0, reviewed_track_id=None) == (
        7,
        "automatic_coverage",
    )


def test_rejects_missing_reviewed_track(tmp_path):
    path = tmp_path / "tracks.csv"
    write_tracks(path, [row(0, 2)])

    with pytest.raises(TrackSelectionError, match="reviewed track 9"):
        select_track_id(
            load_track_observations(path),
            0.0,
            1.0,
            reviewed_track_id=9,
        )


def test_interpolates_only_short_internal_gaps(tmp_path):
    path = tmp_path / "tracks.csv"
    write_tracks(
        path,
        [
            row(0, 4, center_x=10),
            row(2, 4, center_x=30),
            row(8, 4),
        ],
    )
    observations = load_track_observations(path)

    boxes = interpolate_track(
        observations,
        track_id=4,
        start_frame=0,
        end_frame=9,
        max_gap=2,
    )

    assert boxes[1].center_x == pytest.approx(20)
    assert 3 not in boxes
    assert 7 not in boxes

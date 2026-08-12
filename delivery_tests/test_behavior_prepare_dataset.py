import csv
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from cattle_health_app.behavior.prepare_dataset import (
    DatasetPreparationError,
    prepare_dataset,
)


SOURCE_FIELDS = [
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
]


def create_fixture(root: Path):
    video = root / "source.avi"
    writer = cv2.VideoWriter(
        str(video),
        cv2.VideoWriter_fourcc(*"MJPG"),
        10,
        (64, 64),
    )
    assert writer.isOpened()
    for _ in range(40):
        writer.write(np.full((64, 64, 3), 80, dtype=np.uint8))
    writer.release()

    tracks = root / "tracks.csv"
    with tracks.open("w", encoding="utf-8-sig", newline="") as target:
        fields = [
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
        csv_writer = csv.DictWriter(target, fieldnames=fields)
        csv_writer.writeheader()
        for frame in range(40):
            csv_writer.writerow(
                {
                    "frame_index": frame,
                    "time_seconds": frame / 10,
                    "track_id": 8,
                    "class_id": 1,
                    "confidence": 0.9,
                    "center_x": 32,
                    "center_y": 32,
                    "width": 24,
                    "height": 20,
                }
            )

    manifest = root / "source_segments.csv"
    with manifest.open("w", encoding="utf-8-sig", newline="") as target:
        csv_writer = csv.DictWriter(target, fieldnames=SOURCE_FIELDS)
        csv_writer.writeheader()
        csv_writer.writerow(
            {
                "segment_id": "segment-1",
                "source_id": "video-1",
                "video_path": video.name,
                "trajectory_path": tracks.name,
                "dataset": "synthetic",
                "license": "test-only",
                "group_id": "video-1",
                "cattle_id": "unknown",
                "track_id": "8",
                "start_second": "0",
                "end_second": "4",
                "label": "standing",
            }
        )
    return manifest


def test_prepare_dataset_publishes_manifest_and_quality_report(tmp_path):
    manifest = create_fixture(tmp_path)
    output = tmp_path / "behavior_v1"

    result = prepare_dataset(manifest, output, seed=20260730)

    assert result.clip_count == 1
    with (output / "manifests" / "clips.csv").open(
        "r", encoding="utf-8-sig", newline=""
    ) as source:
        clips = list(csv.DictReader(source))
    assert clips[0]["split"] == "train"
    assert clips[0]["selection_method"] == "reviewed"
    clip_path = output / clips[0]["relative_path"]
    assert clip_path.is_file()
    report = json.loads(
        (output / "reports" / "quality_report.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["clip_count"] == 1
    assert report["group_leakage"] is False
    assert report["counts_by_label"] == {"standing": 1}


def test_prepare_dataset_refuses_existing_output(tmp_path):
    manifest = create_fixture(tmp_path)
    output = tmp_path / "behavior_v1"
    output.mkdir()

    with pytest.raises(DatasetPreparationError, match="already exists"):
        prepare_dataset(manifest, output)


def test_prepare_dataset_records_segment_shorter_than_window(tmp_path):
    manifest = create_fixture(tmp_path)
    with manifest.open("a", encoding="utf-8-sig", newline="") as target:
        csv_writer = csv.DictWriter(target, fieldnames=SOURCE_FIELDS)
        csv_writer.writerow(
            {
                "segment_id": "segment-short",
                "source_id": "video-1",
                "video_path": "source.avi",
                "trajectory_path": "tracks.csv",
                "dataset": "synthetic",
                "license": "test-only",
                "group_id": "video-1",
                "cattle_id": "unknown",
                "track_id": "8",
                "start_second": "0",
                "end_second": "2",
                "label": "walking",
            }
        )

    output = tmp_path / "behavior_v1"
    result = prepare_dataset(manifest, output)

    assert result.rejected_count == 1
    with (output / "reports" / "rejected_windows.csv").open(
        "r", encoding="utf-8-sig", newline=""
    ) as source:
        rejected = list(csv.DictReader(source))
    assert rejected[0]["segment_id"] == "segment-short"
    assert rejected[0]["reason"] == "segment_shorter_than_window"

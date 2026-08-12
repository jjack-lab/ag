import csv

import pytest

from cattle_health_app.behavior.manifests import (
    ManifestValidationError,
    load_source_segments,
)


FIELDS = [
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


def write_manifest(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def valid_row(segment_id="segment-1"):
    return {
        "segment_id": segment_id,
        "source_id": "video-1",
        "video_path": "videos/video-1.mp4",
        "trajectory_path": "tracks/video-1.csv",
        "dataset": "CBVD-5",
        "license": "research-use-review-required",
        "group_id": "video-1",
        "cattle_id": "unknown",
        "track_id": "",
        "start_second": "4.0",
        "end_second": "12.0",
        "label": "feeding",
    }


def test_manifest_resolves_paths_and_allows_repeated_source(tmp_path):
    manifest = tmp_path / "source_segments.csv"
    second = valid_row("segment-2")
    second["start_second"] = "12.0"
    second["end_second"] = "20.0"
    second["label"] = "walking"
    second["track_id"] = "7"
    write_manifest(manifest, [valid_row(), second])

    segments = load_source_segments(manifest)

    assert len(segments) == 2
    assert segments[0].video_path == tmp_path / "videos" / "video-1.mp4"
    assert segments[0].reviewed_track_id is None
    assert segments[1].reviewed_track_id == 7
    assert segments[0].source_id == segments[1].source_id


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"segment_id": "segment-1"}, "duplicate segment_id"),
        ({"label": "grazing"}, "Unsupported behavior label"),
        ({"start_second": "9", "end_second": "4"}, "end_second"),
        ({"license": ""}, "license"),
        ({"track_id": "cow-seven"}, "track_id"),
    ],
)
def test_manifest_rejects_invalid_rows(tmp_path, mutation, message):
    manifest = tmp_path / "source_segments.csv"
    first = valid_row()
    second = valid_row("segment-2")
    second.update(mutation)
    write_manifest(manifest, [first, second])

    with pytest.raises(ManifestValidationError, match=message):
        load_source_segments(manifest)

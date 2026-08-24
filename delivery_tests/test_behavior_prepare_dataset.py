import csv
import json
from pathlib import Path

import cv2
import numpy as np
import pytest
import cattle_health_app.behavior.prepare_dataset as prepare_module

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


def test_safe_replace_falls_back_when_home_root_cannot_resolve(tmp_path, monkeypatch):
    staging = tmp_path / "staging"
    output = tmp_path / "published"
    staging.mkdir()
    (staging / "marker.txt").write_text("ready", encoding="utf-8")
    real_resolve = Path.resolve
    home = Path.home()

    def selective_resolve(path, *args, **kwargs):
        if path == home:
            raise PermissionError("restricted home")
        return real_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", selective_resolve)

    prepare_module._safe_replace(staging, output, overwrite=False)

    assert (output / "marker.txt").read_text(encoding="utf-8") == "ready"


def test_safe_replace_keeps_output_resolution_fail_closed(tmp_path, monkeypatch):
    staging = tmp_path / "staging"
    output = tmp_path / "published"
    staging.mkdir()
    real_resolve = Path.resolve

    def fail_output_only(path, *args, **kwargs):
        if path == output:
            raise PermissionError("cannot resolve actual output")
        return real_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", fail_output_only)

    with pytest.raises(PermissionError, match="actual output"):
        prepare_module._safe_replace(staging, output, overwrite=False)

    assert staging.is_dir()
    assert not output.exists()


@pytest.mark.parametrize("samefile_result", [True, PermissionError("cannot compare")])
def test_safe_replace_rejects_existing_alias_when_safety_root_cannot_resolve(
    tmp_path, monkeypatch, samefile_result
):
    staging = tmp_path / "staging"
    output = tmp_path / "existing-alias"
    protected_root = tmp_path / "protected-root-text"
    canonical_root = tmp_path / "protected-root-canonical"
    staging.mkdir()
    output.mkdir()
    protected_root.mkdir()
    real_resolve = Path.resolve
    removals = []

    def selective_resolve(path, *args, **kwargs):
        if path == output:
            return canonical_root
        if path == protected_root:
            raise PermissionError("restricted protected root")
        return real_resolve(path, *args, **kwargs)

    def controlled_samefile(left, right):
        if {Path(left), Path(right)} == {output, protected_root}:
            if isinstance(samefile_result, OSError):
                raise samefile_result
            return samefile_result
        return False

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: protected_root))
    monkeypatch.setattr(Path, "resolve", selective_resolve)
    monkeypatch.setattr(prepare_module.os.path, "samefile", controlled_samefile)
    monkeypatch.setattr(
        prepare_module.shutil,
        "rmtree",
        lambda path: removals.append(Path(path)),
    )

    with pytest.raises(DatasetPreparationError, match="Unsafe|verify"):
        prepare_module._safe_replace(staging, output, overwrite=True)

    assert removals == []
    assert output.is_dir()
    assert staging.is_dir()


@pytest.mark.parametrize("unsafe", [Path.cwd(), Path.home(), Path(Path.cwd().anchor)])
def test_safe_replace_rejects_unsafe_roots_without_removing_them(tmp_path, unsafe, monkeypatch):
    staging = tmp_path / "staging"
    staging.mkdir()
    real_resolve = Path.resolve

    def resolve_known_unsafe_root(path, *args, **kwargs):
        if path == unsafe:
            return Path(prepare_module.os.path.abspath(path))
        return real_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve_known_unsafe_root)

    with pytest.raises(DatasetPreparationError, match="Unsafe output"):
        prepare_module._safe_replace(staging, unsafe, overwrite=True)

    assert staging.is_dir()
    assert unsafe.exists()

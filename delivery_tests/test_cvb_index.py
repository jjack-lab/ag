from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from cattle_health_app.behavior.cvb_index import (
    build_index,
    group_id_for_video,
    parse_ava_row,
    select_frame_numbers,
)


def _jpeg(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    assert cv2.imwrite(str(path), np.full((8, 8, 3), 127, np.uint8))


def _video(root: Path, video_id: str, count: int = 90) -> None:
    for number in range(1, count + 1):
        _jpeg(root / "raw_frames" / video_id / f"img_{number:05d}.jpg")


def _ava(path: Path, rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(rows)


def _row(video: str, timestamp: str = "1", label: str = "2", track: str = "0") -> list[str]:
    return [video, timestamp, "0.1", "0.2", "0.8", "0.9", label, track]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_parse_valid_row_and_rejects_invalid_fields():
    annotation = parse_ava_row(_row("clip", "1.5", "12", "4"))
    assert (annotation.video_id, annotation.timestamp_seconds, annotation.label_id, annotation.track_id) == ("clip", 1.5, 12, 4)
    bad_rows = [
        ["too", "short"],
        _row("clip", "0"),
        _row("clip", "nan"),
        ["clip", "1", "0.8", "0.2", "0.1", "0.9", "2", "0"],
        ["clip", "1", "-0.1", "0.2", "0.8", "0.9", "2", "0"],
        _row("clip", label="13"),
        _row("clip", track="-1"),
    ]
    for row in bad_rows:
        with pytest.raises(ValueError):
            parse_ava_row(row)


def test_timestamp_seconds_selects_shifted_uniform_sixteen_frame_window():
    numbers = select_frame_numbers(1.0, list(range(1, 91)), fps=30.0)
    assert numbers == [1, 5, 9, 13, 17, 21, 25, 29, 32, 36, 40, 44, 48, 52, 56, 60]
    assert len(numbers) == len(set(numbers)) == 16


def test_build_deduplicates_exact_rows_and_reports_conflicting_labels(tmp_path: Path):
    data = tmp_path / "data"
    video = "0002_arm01_gopro1_20200322_222554_beh7_ani1_ins1_cut_1"
    _video(data, video)
    train = data / "train.csv"
    test = data / "test.csv"
    row = _row(video)
    _ava(train, [row, row, _row(video, label="3")])
    _ava(test, [])
    result = build_index(data, train, test, tmp_path / "out")
    assert result.accepted_count == 0
    assert result.rejected_by_reason["conflicting_labels"] == 3


@pytest.mark.parametrize("fault,reason", [("missing", "missing_frame"), ("aria2", "partial_frame"), ("bad", "undecodable_frame")])
def test_rejects_invalid_selected_frames(tmp_path: Path, fault: str, reason: str):
    data = tmp_path / "data"
    _video(data, "clip")
    target_number = 5 if fault == "missing" else 1
    target = data / "raw_frames" / "clip" / f"img_{target_number:05d}.jpg"
    if fault == "missing":
        target.unlink()
    elif fault == "aria2":
        target.with_name(target.name + ".aria2").write_bytes(b"")
    else:
        target.write_bytes(b"not an image")
    train, test = data / "train.csv", data / "test.csv"
    _ava(train, [_row("clip")])
    _ava(test, [])
    result = build_index(data, train, test, tmp_path / "out")
    assert result.rejected_by_reason[reason] == 1


def test_grouping_splits_and_reports_are_deterministic_and_test_is_official(tmp_path: Path):
    data = tmp_path / "data"
    cuts = [
        "0002_arm01_gopro1_20200322_222554_beh7_ani1_ins1_cut_1",
        "0002_arm01_gopro1_20200322_222554_beh8_ani1_ins1_cut_2+0000",
    ]
    other = "0003_arm02_gopro2_20200323_112233_beh1_ani2_ins1_cut_1"
    official = "0002_arm01_gopro1_20200322_222554_beh9_ani1_ins1_cut_3"
    for video in [*cuts, other, official]:
        _video(data, video)
    assert group_id_for_video(cuts[0]) == group_id_for_video(cuts[1]) == "arm01_gopro1_20200322_222554"
    assert group_id_for_video("fallback+0000") == "fallback"
    train, test = data / "train.csv", data / "test.csv"
    _ava(train, [_row(cuts[0]), _row(cuts[1], label="3"), _row(other, label="4"), _row(official, label="12")])
    _ava(test, [_row(official, label="12")])
    out1, out2 = tmp_path / "out1", tmp_path / "out2"
    build_index(data, train, test, out1, seed=20260814)
    build_index(data, train, test, out2, seed=20260814)
    for name in ["train.csv", "val.csv", "test.csv", "rejected.csv", "quality_report.json"]:
        assert (out1 / name).read_bytes() == (out2 / name).read_bytes()
    manifests = {split: _read_csv(out1 / f"{split}.csv") for split in ("train", "val", "test")}
    locations = {row["video_id"]: split for split, rows in manifests.items() for row in rows}
    assert locations[cuts[0]] == locations[cuts[1]] == "test"
    assert locations[official] == "test"
    report = json.loads((out1 / "quality_report.json").read_text(encoding="utf-8"))
    assert set(report["per_class_counts"]) == {str(i) for i in range(1, 13)}
    assert report["group_leakage"] is False
    row = next(row for rows in manifests.values() for row in rows)
    paths = json.loads(row["frame_paths"])
    assert len(paths) == 16 and all(not Path(path).is_absolute() for path in paths)


def test_refuses_overwrite_unless_explicit(tmp_path: Path):
    data = tmp_path / "data"
    _video(data, "clip")
    train, test, output = data / "train.csv", data / "test.csv", tmp_path / "out"
    _ava(train, [_row("clip")])
    _ava(test, [])
    build_index(data, train, test, output)
    with pytest.raises(FileExistsError):
        build_index(data, train, test, output)
    build_index(data, train, test, output, overwrite=True)
    assert (output / "quality_report.json").is_file()





def test_shifts_window_to_non_one_lower_boundary(tmp_path: Path):
    data = tmp_path / "data"
    _video(data, "clip")
    (data / "raw_frames" / "clip" / "img_00001.jpg").unlink()
    train, test = data / "train.csv", data / "test.csv"
    _ava(train, [_row("clip")])
    _ava(test, [])
    result = build_index(data, train, test, tmp_path / "out")
    assert result.accepted_count == 1


def test_failed_overwrite_restores_previous_output(tmp_path: Path, monkeypatch):
    import cattle_health_app.behavior.cvb_index as module
    
    data = tmp_path / "data"
    _video(data, "clip")
    train, test, output = data / "train.csv", data / "test.csv", tmp_path / "out"
    _ava(train, [_row("clip")])
    _ava(test, [])
    build_index(data, train, test, output)
    marker = output / "marker.txt"
    marker.write_text("old", encoding="utf-8")
    real_replace = module.os.replace

    def fail_staging(source, destination):
        if ".staging-" in str(source):
            raise OSError("injected replacement failure")
        return real_replace(source, destination)

    monkeypatch.setattr(module.os, "replace", fail_staging)
    with pytest.raises(OSError, match="injected"):
        build_index(data, train, test, output, overwrite=True)
    assert marker.read_text(encoding="utf-8") == "old"


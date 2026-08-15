from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import numpy as np
import pytest
import cattle_health_app.behavior.cvb_index as indexer

from cattle_health_app.behavior.validate_index import validate_index
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



@pytest.mark.parametrize("video_id", [".", "..", "../outside", "..\\outside", "a/b", "a\\b"])
def test_parse_rejects_video_path_components(video_id: str):
    with pytest.raises(ValueError, match="video_id"):
        parse_ava_row(_row(video_id))


@pytest.mark.parametrize("video_id", ["../../outside", "..\\..\\outside"])
def test_build_blocks_traversal_without_decoding_outside_images(tmp_path: Path, monkeypatch, video_id: str):
    data = tmp_path / "data"
    outside = tmp_path / "outside"
    _video(tmp_path, "outside")
    train, test = data / "train.csv", data / "test.csv"
    _ava(train, [_row(video_id)])
    _ava(test, [])

    def unexpected_decode(*args, **kwargs):
        raise AssertionError("decoder must not read a traversal target")

    monkeypatch.setattr("cattle_health_app.behavior.cvb_index.cv2.imread", unexpected_decode)
    result = build_index(data, train, test, tmp_path / ("out-" + str(abs(hash(video_id)))))
    assert result.accepted_count == 0
    assert result.rejected_by_reason == {"invalid_annotation": 1}


@pytest.mark.parametrize("video_id", ["=bad", "+bad", "-bad", "@bad", " bad", "bad ", "bad.", "CON", "con.txt", "PRN", "AUX.jpg", "NUL", "COM1", "com9.txt", "LPT1", "lpt9.csv", "ébad", "bad\x00id"])
def test_parse_rejects_unsafe_windows_video_ids(video_id: str):
    with pytest.raises(ValueError, match="video_id"):
        parse_ava_row(_row(video_id))


@pytest.mark.parametrize("fps,frame_count,duration", [(0,16,2),(-1,16,2),(float("nan"),16,2),(float("inf"),16,2),(30,0,2),(30,1,2),(30,-1,2),(30,16,0),(30,16,-1),(30,16,float("nan")),(30,16,float("inf"))])
def test_sampling_rejects_invalid_parameters(fps, frame_count, duration):
    with pytest.raises(ValueError):
        select_frame_numbers(1, range(1, 91), fps=fps, frame_count=frame_count, duration_seconds=duration)


def test_same_video_directory_is_scanned_once_for_many_rows(tmp_path: Path, monkeypatch):
    data=tmp_path/"data"; _video(data,"clip")
    train,test=data/"train.csv",data/"test.csv"
    _ava(train, [_row("clip") for _ in range(3000)]); _ava(test,[])
    real_glob=Path.glob; scans=0
    def counted(self, pattern):
        nonlocal scans
        if self.name=="clip" and pattern=="img_*.jpg": scans+=1
        return real_glob(self,pattern)
    monkeypatch.setattr(Path,"glob",counted)
    result=build_index(data,train,test,tmp_path/"out")
    assert result.accepted_count==1 and scans==1


def test_selected_frame_symlink_escape_is_rejected_before_decode(tmp_path: Path, monkeypatch):
    data=tmp_path/"data"; _video(data,"clip")
    external=tmp_path/"external.jpg"; _jpeg(external)
    selected=data/"raw_frames"/"clip"/"img_00001.jpg"; selected.unlink()
    try: selected.symlink_to(external)
    except OSError: pytest.skip("symlinks unavailable")
    train,test=data/"train.csv",data/"test.csv"; _ava(train,[_row("clip")]); _ava(test,[])
    def spy(path,*args,**kwargs):
        assert Path(path).resolve()!=external.resolve()
        return cv2.imread(path,*args,**kwargs)
    monkeypatch.setattr("cattle_health_app.behavior.cvb_index.cv2.imread",spy)
    result=build_index(data,train,test,tmp_path/"out")
    assert result.accepted_count==0 and result.rejected_by_reason["frame_path_escape"]==1


def test_video_directory_symlink_escape_is_rejected_before_scan_or_decode(tmp_path: Path, monkeypatch):
    data=tmp_path/"data"; frames=data/"raw_frames"; frames.mkdir(parents=True)
    external=tmp_path/"external_frames"; _video(tmp_path,"seed")
    (tmp_path/"raw_frames"/"seed").rename(external)
    link=frames/"escape"
    try: link.symlink_to(external, target_is_directory=True)
    except OSError: pytest.skip("directory symlinks unavailable")
    train,test=data/"train.csv",data/"test.csv"; _ava(train,[_row("escape")]); _ava(test,[])
    monkeypatch.setattr("cattle_health_app.behavior.cvb_index.cv2.imread", lambda *args,**kwargs: (_ for _ in ()).throw(AssertionError("must not decode")))
    result=build_index(data,train,test,tmp_path/"out")
    assert result.accepted_count==0 and result.rejected_by_reason["invalid_video_path"]==1


def test_conflict_rejections_preserve_each_actual_occurrence(tmp_path: Path):
    data=tmp_path/"data"; _video(data,"clip")
    train,test=data/"train.csv",data/"test.csv"
    _ava(train,[_row("clip",label="2"),_row("clip",label="2"),_row("clip",label="3")])
    _ava(test,[_row("clip",label="3")])
    result=build_index(data,train,test,tmp_path/"out")
    rows=_read_csv(tmp_path/"out"/"rejected.csv")
    provenance=[(r["source_split"],int(r["row_number"])) for r in rows]
    assert result.rejected_count==4
    assert provenance==[("test",1),("train",1),("train",2),("train",3)]


def test_raw_frames_root_symlink_escape_is_rejected_before_decode(tmp_path: Path, monkeypatch):
    data=tmp_path/"data"; data.mkdir(); external=tmp_path/"external"; external.mkdir()
    try: (data/"raw_frames").symlink_to(external,target_is_directory=True)
    except OSError: pytest.skip("directory symlinks unavailable")
    train,test=data/"train.csv",data/"test.csv"; _ava(train,[_row("clip")]); _ava(test,[])
    monkeypatch.setattr("cattle_health_app.behavior.cvb_index.cv2.imread",lambda *a,**k: (_ for _ in ()).throw(AssertionError("must not decode")))
    with pytest.raises(ValueError,match="raw_frames"):
        build_index(data,train,test,tmp_path/"out")


def test_streams_thousands_of_mostly_unique_rows_through_disk_spool(tmp_path: Path):
    from cattle_health_app.behavior.cvb_index import _iter_annotations

    data = tmp_path / "data"
    _video(data, "clip")
    train, test = data / "train.csv", data / "test.csv"
    rows = [_row("clip", timestamp=f"{1 + index / 100000:.5f}") for index in range(2000)]
    _ava(train, rows)
    _ava(test, [])
    iterator = _iter_annotations(train, "train")
    assert iter(iterator) is iterator
    iterator.close()
    result = build_index(data, train, test, tmp_path / "out")
    assert result.accepted_count == 2000


def test_prepare_script_keeps_generated_index_in_current_worktree():
    script = (Path(__file__).parents[1] / "scripts" / "prepare_cvb_behavior.ps1").read_text(
        encoding="utf-8"
    )
    assert "$projectRoot=Split-Path -Parent $PSScriptRoot" in script
    assert "Join-Path $projectRoot 'data\\cvb_behavior_v1'" in script

def test_rebalance_moves_the_minimum_whole_groups_without_leakage():
    connection = indexer.sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE accepted(label_id INTEGER, group_id TEXT, split TEXT)")
    connection.executemany("INSERT INTO accepted VALUES (?,?,?)",
        [(label,"train-base","train") for label in range(1,11)]
        + [(11,"val-both","val"),(12,"val-both","val")]
        + [(11,"val-eleven","val"),(12,"test-twelve","test")])
    moves=indexer._ensure_training_class_coverage(connection,seed=20260814)
    assert moves == [{"group_id":"val-both","from_split":"val","to_split":"train","labels":[11,12],"row_count":2}]
    assert set(row[0] for row in connection.execute("SELECT DISTINCT label_id FROM accepted WHERE split='train'")) == set(range(1,13))
    assert all(row[1] == 1 for row in connection.execute("SELECT group_id,COUNT(DISTINCT split) FROM accepted GROUP BY group_id"))

def test_quality_report_lists_missing_classes_and_split_deviation(tmp_path: Path):
    data=tmp_path/"data"; _video(data,"train-a"); _video(data,"test-b")
    train,test=data/"train.csv",data/"test.csv"
    _ava(train,[_row("train-a",label=str(label),track=str(label)) for label in range(1,12)])
    _ava(test,[_row("test-b",label="12")])
    output=tmp_path/"out"; build_index(data,train,test,output)
    report=json.loads((output/"quality_report.json").read_text(encoding="utf-8"))
    assert report["per_split_missing_classes"]["train"] == []
    assert report["split_adjustments"][0]["from_split"] == "test"
    assert report["official_test_split_modified"] is True

def test_training_wrapper_logs_native_stderr_without_treating_warnings_as_fatal():
    script=(Path(__file__).parents[1]/"scripts"/"train_cvb_behavior.ps1").read_text(encoding="utf-8")
    assert "$ErrorActionPreference='Continue'" in script
    assert "$processExitCode=$LASTEXITCODE" in script
    assert "UTF8Encoding($false)" in script
    assert "AppendAllText($log" in script

def test_validator_rejects_quality_claim_mismatch_and_publishes_atomically(tmp_path: Path):
    data=tmp_path/"data"; _video(data,"clip")
    train,test=data/"train.csv",data/"test.csv"; _ava(train,[_row("clip")]); _ava(test,[])
    index=tmp_path/"index"; build_index(data,train,test,index)
    quality=json.loads((index/"quality_report.json").read_text(encoding="utf-8"))
    quality["per_split_counts"]["train"]+=1
    (index/"quality_report.json").write_text(json.dumps(quality),encoding="utf-8")
    output=tmp_path/"validation.json"
    evidence=validate_index(index,data,output)
    assert evidence["success"] is False
    assert any("per_split_counts.train" in error for error in evidence["errors"])
    assert json.loads(output.read_text(encoding="utf-8"))["success"] is False
    assert not list(tmp_path.glob(".validation.json.tmp-*"))

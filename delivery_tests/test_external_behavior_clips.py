import csv
from dataclasses import replace

import pytest

from cattle_health_app.behavior.external_clips import (
    ClipManifestError,
    assign_groups,
    deterministic_class_cap,
    make_clip_record,
    validate_no_group_leakage,
    write_clip_manifest,
)


def _record(video_id="618", start=2.0, label="grazing", track="1"):
    return make_clip_record(
        dataset_id="cbvd5",
        dataset_version="11",
        source_video_id=video_id,
        source_video_path="data/external/cbvd5/raw/videos/videos/{}.mp4".format(
            video_id
        ),
        camera_id="unknown",
        start_second=start,
        end_second=start + 4.0,
        track_id=track,
        source_labels=("standing", "foraging"),
        mapped_label=label,
        mapping_tier="strict",
        crop_box=(0.1, 0.2, 0.4, 0.7),
        transformations=("context_margin:0.15",),
        output_path="data/external/cbvd5/derived/{}.mp4".format(video_id),
        output_sha256="a" * 64,
        group_block_seconds=60,
    )


def test_ids_are_stable_and_change_with_source_identity():
    first = _record()
    assert first.sample_id == _record().sample_id
    assert first.source_group_id == _record(start=20).source_group_id
    assert first.sample_id != _record(track="2").sample_id
    assert first.source_group_id != _record(video_id="619").source_group_id


def test_default_external_assignment_is_test_only():
    assigned = assign_groups([_record(), _record(video_id="619")], seed=20260823)
    assert {item.split for item in assigned} == {"test"}


def test_split_groups_never_cross_boundaries():
    same_group = [_record(start=2), _record(start=10, track="2")]
    records = same_group + [_record(video_id=str(700 + index)) for index in range(8)]
    split = assign_groups(records, seed=20260823, ratios=(0.5, 0.25, 0.25))
    owners = {}
    for item in split:
        assert owners.setdefault(item.source_group_id, item.split) == item.split
    validate_no_group_leakage(split)


def test_validator_rejects_group_leakage():
    record = _record()
    other_sample = _record(start=10, track="2")
    with pytest.raises(ClipManifestError, match="group leakage"):
        validate_no_group_leakage(
            [replace(record, split="train"), replace(other_sample, split="test")]
        )


def test_class_cap_is_deterministic_and_balanced():
    rows = [
        _record(video_id=str(index), label="grazing") for index in range(10)
    ] + [_record(video_id=str(100 + index), label="drinking") for index in range(7)]
    selected = deterministic_class_cap(rows, max_per_class=3, seed=20260823)
    again = deterministic_class_cap(list(reversed(rows)), 3, seed=20260823)
    assert [row.sample_id for row in selected] == [row.sample_id for row in again]
    assert sum(row.mapped_label == "grazing" for row in selected) == 3
    assert sum(row.mapped_label == "drinking" for row in selected) == 3


def test_manifest_writer_preserves_provenance_columns(tmp_path):
    path = tmp_path / "evaluation_clips.csv"
    record = replace(_record(), split="test")

    write_clip_manifest(path, [record])

    with path.open("r", encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["sample_id"] == record.sample_id
    assert row["source_group_id"] == record.source_group_id
    assert row["source_video_path"].endswith("618.mp4")
    assert row["source_labels"] == '["standing", "foraging"]'
    assert row["transformations"] == '["context_margin:0.15"]'
    assert row["output_sha256"] == "a" * 64


@pytest.mark.parametrize(
    "change,match",
    [
        ({"end_second": 1.0}, "time range"),
        ({"mapping_tier": "invented"}, "mapping_tier"),
        ({"output_sha256": "bad"}, "SHA-256"),
        ({"crop_box": (0.5, 0.2, 0.4, 0.7)}, "crop_box"),
    ],
)
def test_manifest_record_rejects_invalid_evidence(change, match):
    kwargs = dict(
        dataset_id="cbvd5",
        dataset_version="11",
        source_video_id="618",
        source_video_path="data/external/cbvd5/raw/videos/videos/618.mp4",
        camera_id="unknown",
        start_second=2.0,
        end_second=6.0,
        track_id="1",
        source_labels=("standing", "foraging"),
        mapped_label="grazing",
        mapping_tier="strict",
        crop_box=(0.1, 0.2, 0.4, 0.7),
        transformations=("context_margin:0.15",),
        output_path="data/external/cbvd5/derived/618.mp4",
        output_sha256="a" * 64,
    )
    kwargs.update(change)
    with pytest.raises(ClipManifestError, match=match):
        make_clip_record(**kwargs)

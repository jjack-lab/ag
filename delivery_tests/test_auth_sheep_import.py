import csv
import json

import pytest

from scripts.import_auth_sheep import convert_annotations


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_convert_auth_sheep_uses_hbb_and_cvat_track_ids(tmp_path):
    images = [
        {"id": 1, "width": 100, "height": 50, "file_name": "video1_1"},
        {"id": 2, "width": 100, "height": 50, "file_name": "video1_2"},
    ]
    boxes = [
        {"id": 10, "image_id": 1, "category_id": 1, "bbox": [10, 5, 20, 10]},
        {"id": 11, "image_id": 1, "category_id": 2, "bbox": [2, 2, 5, 5]},
        {"id": 12, "image_id": 2, "category_id": 1, "bbox": [20, 10, 10, 5]},
    ]
    tracks = [
        {"id": 10, "image_id": 1, "category_id": 1, "attributes": {"track_id": 7}},
        {"id": 11, "image_id": 1, "category_id": 2, "attributes": {"track_id": 8}},
        {"id": 12, "image_id": 2, "category_id": 1, "attributes": {"track_id": 7}},
    ]
    hbb, cvat, output = (tmp_path / name for name in ("hbb.json", "cvat.json", "truth.csv"))
    _write_json(hbb, {"images": images, "categories": [{"id": 1, "name": "sheep"},
                                                       {"id": 2, "name": "human"}], "annotations": boxes})
    _write_json(cvat, {"annotations": tracks})

    result = convert_annotations(hbb, cvat, output)

    with output.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert result == {"labeled_frames": 2, "sheep_boxes": 2, "human_boxes_skipped": 1,
                      "goat_boxes_skipped": 0, "clipped_boxes": 0}
    assert rows == [
        {"frame_index": "0", "class_id": "0", "track_id": "7", "x": "0.1", "y": "0.1", "width": "0.2", "height": "0.2"},
        {"frame_index": "1", "class_id": "0", "track_id": "7", "x": "0.2", "y": "0.2", "width": "0.1", "height": "0.1"},
    ]


def test_convert_auth_sheep_rejects_mismatched_annotations(tmp_path):
    hbb, cvat, output = (tmp_path / name for name in ("hbb.json", "cvat.json", "truth.csv"))
    _write_json(hbb, {"images": [{"id": 1, "width": 100, "height": 50}], "annotations": [
        {"id": 10, "image_id": 1, "category_id": 1, "bbox": [10, 5, 20, 10]}
    ]})
    _write_json(cvat, {"annotations": [
        {"id": 10, "image_id": 2, "category_id": 1, "attributes": {"track_id": 7}}
    ]})
    with pytest.raises(ValueError, match="mismatch"):
        convert_annotations(hbb, cvat, output)
    assert not output.exists()


def test_convert_auth_sheep_clips_partially_outside_boxes(tmp_path):
    hbb, cvat, output = (tmp_path / name for name in ("hbb.json", "cvat.json", "truth.csv"))
    _write_json(hbb, {"images": [{"id": 1, "width": 100, "height": 50}], "annotations": [
        {"id": 10, "image_id": 1, "category_id": 1, "bbox": [95, 5, 20, 10]}
    ]})
    _write_json(cvat, {"annotations": [
        {"id": 10, "image_id": 1, "category_id": 1, "attributes": {"track_id": 7}}
    ]})
    result = convert_annotations(hbb, cvat, output)
    with output.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert result["clipped_boxes"] == 1
    assert rows[0]["x"] == "0.95"
    assert rows[0]["width"] == "0.05"


def test_convert_auth_sheep_rounds_border_box_inside_unit_square(tmp_path):
    hbb, cvat, output = (tmp_path / name for name in ("hbb.json", "cvat.json", "truth.csv"))
    _write_json(hbb, {"images": [{"id": 1, "width": 3840, "height": 2160}], "annotations": [
        {"id": 10, "image_id": 1, "category_id": 1,
         "bbox": [677.7354309858139, 1967.50748453799, 332.34913802837207, 334.55503092402023]}
    ]})
    _write_json(cvat, {"annotations": [
        {"id": 10, "image_id": 1, "category_id": 1, "attributes": {"track_id": 7}}
    ]})
    convert_annotations(hbb, cvat, output)
    with output.open(encoding="utf-8", newline="") as stream:
        row = next(csv.DictReader(stream))
    assert float(row["y"]) + float(row["height"]) <= 1.0


def test_convert_auth_sheep_skips_goats_and_humans_by_category_name(tmp_path):
    hbb, cvat, output = (tmp_path / name for name in ("hbb.json", "cvat.json", "truth.csv"))
    annotations = [
        {"id": index, "image_id": 1, "category_id": index, "bbox": [index * 10, 5, 5, 5]}
        for index in (1, 2, 3)
    ]
    _write_json(hbb, {"images": [{"id": 1, "width": 100, "height": 50}],
                      "categories": [{"id": 1, "name": "sheep"}, {"id": 2, "name": "goat"},
                                     {"id": 3, "name": "human"}], "annotations": annotations})
    _write_json(cvat, {"annotations": [
        {"id": row["id"], "image_id": 1, "category_id": row["category_id"],
         "attributes": {"track_id": row["id"]}} for row in annotations
    ]})
    result = convert_annotations(hbb, cvat, output)
    with output.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 1
    assert result["goat_boxes_skipped"] == 1
    assert result["human_boxes_skipped"] == 1

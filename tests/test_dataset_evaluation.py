import csv
from pathlib import Path

from cattle_health_app.dataset_evaluation import evaluate_annotations


def write_csv(path, fields, rows):
    with Path(path).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_evaluation_matches_boxes_on_labeled_frames_and_counts_id_switch(tmp_path):
    truth = tmp_path / "truth.csv"
    predictions = tmp_path / "predictions.csv"
    write_csv(truth, ["frame_index", "class_id", "track_id", "x", "y", "width", "height"], [
        {"frame_index": 0, "class_id": 1, "track_id": 10, "x": .1, "y": .2, "width": .2, "height": .2},
        {"frame_index": 1, "class_id": 1, "track_id": 10, "x": .1, "y": .2, "width": .2, "height": .2},
        {"frame_index": 2, "class_id": 1, "track_id": 10, "x": .1, "y": .2, "width": .2, "height": .2},
    ])
    write_csv(predictions, ["frame_index", "class_id", "track_id", "center_x", "center_y", "width", "height"], [
        {"frame_index": 0, "class_id": 1, "track_id": 7, "center_x": 20, "center_y": 30, "width": 20, "height": 20},
        {"frame_index": 1, "class_id": 1, "track_id": 8, "center_x": 20, "center_y": 30, "width": 20, "height": 20},
        {"frame_index": 2, "class_id": 1, "track_id": 8, "center_x": 80, "center_y": 30, "width": 20, "height": 20},
        {"frame_index": 3, "class_id": 1, "track_id": 9, "center_x": 20, "center_y": 30, "width": 20, "height": 20},
    ])
    result = evaluate_annotations(truth, predictions, width=100, height=100, class_id=1)
    assert result == {"labeled_frames": 3, "ground_truth_boxes": 3,
                      "true_positive": 2, "false_positive": 1, "false_negative": 1,
                      "precision": 2 / 3, "recall": 2 / 3, "f1": 2 / 3,
                      "id_switches": 1, "iou_threshold": 0.5}


def test_evaluation_rejects_bad_or_mixed_annotations(tmp_path):
    truth = tmp_path / "truth.csv"
    predictions = tmp_path / "predictions.csv"
    write_csv(predictions, ["frame_index", "class_id", "track_id", "center_x", "center_y", "width", "height"], [])
    write_csv(truth, ["frame_index", "class_id", "track_id", "x", "y", "width", "height"], [
        {"frame_index": 0, "class_id": 0, "track_id": 1, "x": .9, "y": .2, "width": .2, "height": .2},
    ])
    import pytest
    with pytest.raises(ValueError):
        evaluate_annotations(truth, predictions, width=100, height=100, class_id=0)
    write_csv(truth, ["frame_index", "class_id", "track_id", "x", "y", "width", "height"], [
        {"frame_index": 0, "class_id": 1, "track_id": 1, "x": .1, "y": .2, "width": .2, "height": .2},
    ])
    with pytest.raises(ValueError, match="class_id"):
        evaluate_annotations(truth, predictions, width=100, height=100, class_id=0)
    with pytest.raises(ValueError, match="video length"):
        evaluate_annotations(truth, predictions, width=100, height=100, class_id=1, frame_count=0)

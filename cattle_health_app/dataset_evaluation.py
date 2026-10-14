"""Reproducible box matching for one annotated public video sequence.

Ground truth uses normalized top-left xywh. Tracker CSV uses pixel center xywh.
Only frames containing at least one annotation are evaluated; this is explicit in
the report because unlabeled frames must not be treated as negative examples.
"""

import csv
import math


TRUTH_FIELDS = {"frame_index", "class_id", "track_id", "x", "y", "width", "height"}
PREDICTION_FIELDS = {"frame_index", "class_id", "track_id", "center_x", "center_y", "width", "height"}


def _read_rows(path, fields):
    with open(path, encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not fields.issubset(reader.fieldnames):
            raise ValueError("CSV missing required columns: " + ", ".join(sorted(fields)))
        return list(reader)


def _integer(value, name):
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Invalid {name}") from error
    if parsed < 0:
        raise ValueError(f"Invalid {name}")
    return parsed


def _number(value, name):
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Invalid {name}") from error
    if not math.isfinite(parsed):
        raise ValueError(f"Invalid {name}")
    return parsed


def _iou(left, right):
    x1, y1 = max(left[0], right[0]), max(left[1], right[1])
    x2, y2 = min(left[2], right[2]), min(left[3], right[3])
    overlap = max(0, x2 - x1) * max(0, y2 - y1)
    area_left = (left[2] - left[0]) * (left[3] - left[1])
    area_right = (right[2] - right[0]) * (right[3] - right[1])
    return overlap / (area_left + area_right - overlap) if overlap else 0.0


def evaluate_annotations(truth_path, predictions_path, width, height, class_id, iou_threshold=0.5, frame_count=None):
    if width <= 0 or height <= 0 or class_id not in (0, 1):
        raise ValueError("Invalid video dimensions or class_id")
    truth = {}
    seen = set()
    for row in _read_rows(truth_path, TRUTH_FIELDS):
        frame = _integer(row["frame_index"], "frame_index")
        if frame_count is not None and frame >= frame_count:
            raise ValueError("Ground truth frame_index exceeds video length")
        species = _integer(row["class_id"], "class_id")
        track = _integer(row["track_id"], "track_id")
        if species != class_id:
            raise ValueError("Ground truth class_id does not match video species")
        if (frame, track) in seen:
            raise ValueError("Duplicate ground truth track ID in one frame")
        seen.add((frame, track))
        x, y, box_w, box_h = (_number(row[key], key) for key in ("x", "y", "width", "height"))
        if min(x, y) < 0 or min(box_w, box_h) <= 0 or x + box_w > 1 or y + box_h > 1:
            raise ValueError("Ground truth box must fit normalized [0, 1] frame")
        truth.setdefault(frame, []).append((track, (x * width, y * height, (x + box_w) * width, (y + box_h) * height)))
    if not truth:
        raise ValueError("Ground truth CSV has no annotated frames")
    predictions = {}
    for row in _read_rows(predictions_path, PREDICTION_FIELDS):
        frame = _integer(row["frame_index"], "frame_index")
        species = _integer(row["class_id"], "class_id")
        if frame not in truth or species != class_id:
            continue
        track = _integer(row["track_id"], "track_id")
        x, y, box_w, box_h = (_number(row[key], key) for key in ("center_x", "center_y", "width", "height"))
        if box_w <= 0 or box_h <= 0:
            raise ValueError("Prediction box dimensions must be positive")
        predictions.setdefault(frame, []).append((track, (x - box_w / 2, y - box_h / 2, x + box_w / 2, y + box_h / 2)))
    tp = fp = fn = id_switches = 0
    last_predicted_id = {}
    for frame in sorted(truth):
        actual = truth[frame]
        predicted = predictions.get(frame, [])
        candidates = sorted(((_iou(a_box, p_box), a_index, p_index)
                             for a_index, (_, a_box) in enumerate(actual)
                             for p_index, (_, p_box) in enumerate(predicted)), reverse=True)
        matched_actual, matched_predicted = set(), set()
        for score, a_index, p_index in candidates:
            if score < iou_threshold:
                break
            if a_index in matched_actual or p_index in matched_predicted:
                continue
            matched_actual.add(a_index)
            matched_predicted.add(p_index)
            actual_id, predicted_id = actual[a_index][0], predicted[p_index][0]
            if actual_id in last_predicted_id and last_predicted_id[actual_id] != predicted_id:
                id_switches += 1
            last_predicted_id[actual_id] = predicted_id
        tp += len(matched_actual)
        fp += len(predicted) - len(matched_predicted)
        fn += len(actual) - len(matched_actual)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"labeled_frames": len(truth), "ground_truth_boxes": sum(map(len, truth.values())),
            "true_positive": tp, "false_positive": fp, "false_negative": fn,
            "precision": precision, "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            "id_switches": id_switches, "iou_threshold": iou_threshold}

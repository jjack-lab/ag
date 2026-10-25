"""Evaluate sheep tracking boxes on an independently annotated video."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import cv2

from cattle_health_app.dataset_evaluation import evaluate_annotations


FIELDS = (
    "frame_index", "class_id", "track_id", "center_x", "center_y",
    "width", "height", "confidence",
)


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def score_existing_predictions(
    video_path, truth_path, predictions_path, report_path,
    capture_factory=cv2.VideoCapture,
):
    capture = capture_factory(str(video_path))
    if not capture.isOpened():
        raise ValueError("video cannot be opened")
    try:
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        capture.release()
    if min(width, height, frame_count) <= 0:
        raise ValueError("invalid video metadata")
    predictions = Path(predictions_path)
    metrics = evaluate_annotations(
        truth_path, predictions, width, height, 0,
        iou_threshold=0.5, frame_count=frame_count,
    )
    with predictions.open(encoding="utf-8", newline="") as stream:
        metrics["prediction_boxes"] = sum(1 for _ in csv.DictReader(stream))
    metrics["decoded_frames"] = frame_count
    report = Path(report_path)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return metrics


def run_evaluation(
    video_path, truth_path, model, predictions_path, report_path,
    conf=0.25, iou=0.45, device=None, capture_factory=cv2.VideoCapture,
):
    capture = capture_factory(str(video_path))
    if not capture.isOpened():
        raise ValueError("video cannot be opened")
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if min(width, height, frame_count) <= 0:
        capture.release()
        raise ValueError("invalid video metadata")
    rows = []
    try:
        for frame_index in range(frame_count):
            okay, frame = capture.read()
            if not okay:
                raise ValueError("video ended before declared frame count")
            options = {
                "classes": [0], "persist": True, "tracker": "bytetrack.yaml",
                "conf": conf, "iou": iou, "imgsz": 640, "verbose": False,
            }
            if device:
                options["device"] = device
            boxes = model.track(frame, **options)[0].boxes
            if boxes.id is None:
                continue
            for track, species, geometry, confidence in zip(
                boxes.id.cpu().tolist(), boxes.cls.cpu().tolist(),
                boxes.xywh.cpu().tolist(), boxes.conf.cpu().tolist(),
            ):
                center_x, center_y, box_width, box_height = geometry
                rows.append({
                    "frame_index": frame_index, "class_id": int(species),
                    "track_id": int(track), "center_x": center_x,
                    "center_y": center_y, "width": box_width,
                    "height": box_height, "confidence": confidence,
                })
    finally:
        capture.release()

    predictions = Path(predictions_path)
    predictions.parent.mkdir(parents=True, exist_ok=True)
    with predictions.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return score_existing_predictions(
        video_path, truth_path, predictions, report_path,
        capture_factory=capture_factory,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--truth", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default=None)
    parser.add_argument("--reuse-predictions", action="store_true")
    arguments = parser.parse_args()
    arguments.output.mkdir(parents=True, exist_ok=True)
    if arguments.reuse_predictions:
        metrics = score_existing_predictions(
            arguments.video, arguments.truth,
            arguments.output / "predictions.csv", arguments.output / "metrics.json",
        )
    else:
        from ultralytics import YOLO
        metrics = run_evaluation(
            arguments.video, arguments.truth, YOLO(str(arguments.model)),
            arguments.output / "predictions.csv", arguments.output / "metrics.json",
            device=arguments.device,
        )
    provenance = {
        "video_sha256": _sha256(arguments.video),
        "truth_sha256": _sha256(arguments.truth),
        "model_sha256": _sha256(arguments.model),
        "prediction_sha256": _sha256(arguments.output / "predictions.csv"),
        "confidence": 0.25, "nms_iou": 0.45, "match_iou": 0.5,
        "tracker": "bytetrack.yaml", "image_size": 640,
    }
    (arguments.output / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(metrics, ensure_ascii=False))


if __name__ == "__main__":
    main()

from __future__ import annotations

import csv
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

import cv2

from cattle_health_app.behavior.reporting import (
    BehaviorObservation,
    build_behavior_summary,
    write_behavior_report,
    write_behavior_summary,
    write_behavior_timeline,
)
from health_monitor import CattleHealthMonitor, DetectionObservation, HealthConfig
from inference_profile import build_track_kwargs

LOGGER = logging.getLogger(__name__)
UNCERTAIN_IDS = frozenset((1, 10, 11))
MAX_DECODE_RETRIES = 2


@dataclass(frozen=True)
class TrackingVideoResult:
    video_path: Path
    trajectory_csv: Path
    alert_csv: Path
    health_summary_csv: Path
    health_report_html: Path
    frame_count: int
    tracked_cattle: int
    alert_count: int
    behavior_csv: Optional[Path] = None
    behavior_summary_csv: Optional[Path] = None
    behavior_report_json: Optional[Path] = None
    behavior_model_status: str = "unavailable"
    behavior_model_version: Optional[str] = None
    behavior_summary: list = field(default_factory=list)
    decode_error_count: int = 0

    def to_dict(self, media_root=None) -> dict:
        root = Path(media_root).resolve() if media_root else None

        def display(path):
            if path is None:
                return None
            resolved = path.resolve()
            return resolved.relative_to(root).as_posix() if root else resolved.as_posix()

        return {
            "video_path": display(self.video_path),
            "trajectory_csv": display(self.trajectory_csv),
            "alert_csv": display(self.alert_csv),
            "health_summary_csv": display(self.health_summary_csv),
            "health_report_html": display(self.health_report_html),
            "frame_count": self.frame_count,
            "tracked_cattle": self.tracked_cattle,
            "alert_count": self.alert_count,
            "behavior_csv": display(self.behavior_csv),
            "behavior_summary_csv": display(self.behavior_summary_csv),
            "behavior_report_json": display(self.behavior_report_json),
            "behavior_model_status": self.behavior_model_status,
            "behavior_model_version": self.behavior_model_version,
            "behavior_summary": list(self.behavior_summary),
            "decode_error_count": self.decode_error_count,
        }


def _geometry_xywh(frame, xywh: Sequence[float], context: float = 0.15):
    if frame is None or getattr(frame, "ndim", 0) != 3 or frame.size == 0:
        return None, (0, 12)
    frame_height, frame_width = frame.shape[:2]
    try:
        valid_length = len(xywh) == 4
    except TypeError:
        valid_length = False
    if not valid_length or not math.isfinite(float(context)) or context < 0:
        return None, (0, 12)
    try:
        x, y, width, height = map(float, xywh)
    except (TypeError, ValueError, OverflowError):
        return None, (0, 12)
    if not all(math.isfinite(value) for value in (x, y, width, height)):
        return None, (0, 12)
    fallback = (
        min(max(int(round(x)), 0), max(frame_width - 1, 0)),
        min(max(int(round(y)) - 8, 12), max(frame_height - 1, 12)),
    )
    if width <= 0 or height <= 0:
        return None, fallback
    expanded_width = width * (1 + 2 * context)
    expanded_height = height * (1 + 2 * context)
    left = max(0, int(math.floor(x - expanded_width / 2)))
    right = min(frame_width, int(math.ceil(x + expanded_width / 2)))
    top = max(0, int(math.floor(y - expanded_height / 2)))
    bottom = min(frame_height, int(math.ceil(y + expanded_height / 2)))
    anchor = (left, max(12, top - 6))
    if right <= left or bottom <= top:
        return None, fallback
    crop = frame[top:bottom, left:right]
    return (crop.copy() if crop.size else None), anchor


def _crop_xywh(frame, xywh: Sequence[float], context: float = 0.15):
    return _geometry_xywh(frame, xywh, context)[0]


def _draw_status(frame, anchor, track_id: int, text: str) -> None:
    cv2.putText(
        frame,
        "ID {} {}".format(track_id, text),
        anchor,
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )


def _uncertain_observation(track_id, frame_index, fps, version, confidence=0.0):
    return BehaviorObservation(
        frame_index=frame_index,
        time_seconds=frame_index / fps,
        track_id=track_id,
        label_id=1,
        label="none",
        display_name="无法确定",
        confidence=float(confidence),
        health_eligible=False,
        model_version=version or "unavailable",
    )


def _prediction_observation(prediction, fps, threshold):
    timestamp = prediction.timestamp_seconds
    if timestamp is None:
        timestamp = prediction.frame_index / fps
    uncertain = (
        prediction.label_id in UNCERTAIN_IDS
        or not prediction.health_eligible
        or prediction.confidence < threshold
    )
    if uncertain:
        return BehaviorObservation(
            prediction.frame_index,
            timestamp,
            prediction.track_id,
            1,
            "none",
            "无法确定",
            prediction.confidence,
            False,
            prediction.model_version,
        )
    return BehaviorObservation(
        prediction.frame_index,
        timestamp,
        prediction.track_id,
        prediction.label_id,
        prediction.label,
        prediction.display_name,
        prediction.confidence,
        True,
        prediction.model_version,
    )


def _read_frame(capture, total_frames):
    success, frame = capture.read()
    if success:
        return frame, 0, False
    position = max(0, int(capture.get(cv2.CAP_PROP_POS_FRAMES)))
    if total_frames <= 0 or position >= total_frames:
        return None, 0, True
    errors = 1
    for _ in range(MAX_DECODE_RETRIES):
        success, frame = capture.read()
        if success:
            return frame, errors, False
        errors += 1
    raise RuntimeError(
        "video decode failed after {} consecutive errors at frame {}".format(
            errors, position
        )
    )


def process_tracked_video(
    model,
    source_path,
    output_dir,
    conf,
    iou,
    class_id=1,
    tracker="bytetrack.yaml",
    progress_callback=None,
    behavior_runtime=None,
) -> TrackingVideoResult:
    source = Path(source_path)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise ValueError("Unable to open video: {}".format(source))

    fps = capture.get(cv2.CAP_PROP_FPS) or 20.0
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = max(0, int(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
    video_path = root / "{}_tracked.mp4".format(source.stem)
    video_writer = cv2.VideoWriter(
        str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
    )
    if not video_writer.isOpened():
        capture.release()
        video_writer.release()
        video_path.unlink(missing_ok=True)
        raise ValueError("Unable to create tracked video: {}".format(video_path))

    monitor = CattleHealthMonitor(HealthConfig(fps=fps, cattle_class_ids={class_id}))
    rows = []
    behavior_rows = []
    track_ids_seen = set()
    frame_index = 0
    decode_error_count = 0
    behavior_status = "ready" if behavior_runtime is not None else "unavailable"
    behavior_version = (
        getattr(behavior_runtime, "model_version", None)
        if behavior_runtime is not None
        else None
    )
    behavior_error = None
    processing_failed = False

    try:
        while True:
            frame, decode_errors, eof = _read_frame(capture, total_frames)
            decode_error_count += decode_errors
            if eof:
                break
            track_kwargs = build_track_kwargs(conf, iou, class_id)
            track_kwargs["tracker"] = tracker
            result = model.track(frame, **track_kwargs)[0]
            health_observations = []
            behavior_inputs = []
            frame_tracks = {}
            if result.boxes.id is not None:
                ids = result.boxes.id.int().cpu().tolist()
                boxes = result.boxes.xywh.cpu().tolist()
                classes = result.boxes.cls.int().cpu().tolist()
                confidences = result.boxes.conf.cpu().tolist()
                for track_id, box, detected_class, confidence in zip(
                    ids, boxes, classes, confidences
                ):
                    track_id = int(track_id)
                    x, y, box_width, box_height = map(float, box)
                    crop, anchor = _geometry_xywh(frame, box)
                    frame_tracks[track_id] = anchor
                    track_ids_seen.add(track_id)
                    rows.append(
                        {
                            "frame_index": frame_index,
                            "time_seconds": frame_index / fps,
                            "track_id": track_id,
                            "class_id": detected_class,
                            "confidence": confidence,
                            "center_x": x,
                            "center_y": y,
                            "width": box_width,
                            "height": box_height,
                        }
                    )
                    health_observations.append(
                        DetectionObservation(
                            track_id=track_id,
                            class_id=detected_class,
                            confidence=float(confidence),
                            xywh=(x, y, box_width, box_height),
                        )
                    )
                    if behavior_status == "ready" and crop is not None:
                        behavior_inputs.append(
                            (track_id, frame_index, crop, frame_index / fps)
                        )

            monitor.update(frame_index, health_observations)
            annotated = result.plot()
            predictions = {}
            if behavior_inputs and behavior_status == "ready":
                try:
                    returned = behavior_runtime.observe_batch(behavior_inputs)
                    predictions = {item.track_id: item for item in returned}
                except Exception as exc:
                    behavior_status = "error"
                    behavior_error = "{}: {}".format(type(exc).__name__, exc)
                    LOGGER.exception("Behavior inference disabled for this video")

            threshold = getattr(behavior_runtime, "confidence_threshold", 0.45)
            for track_id, anchor in frame_tracks.items():
                prediction = predictions.get(track_id)
                if prediction is None:
                    observation = _uncertain_observation(
                        track_id, frame_index, fps, behavior_version
                    )
                    _draw_status(
                        annotated,
                        anchor,
                        track_id,
                        "行为待识别/无法确定 0%",
                    )
                else:
                    observation = _prediction_observation(prediction, fps, threshold)
                    _draw_status(
                        annotated,
                        anchor,
                        track_id,
                        "{} {:.0f}%".format(
                            observation.display_name, observation.confidence * 100
                        ),
                    )
                behavior_rows.append(observation)

            video_writer.write(annotated)
            frame_index += 1
            if progress_callback and total_frames:
                progress_callback(min(0.99, frame_index / total_frames))
    except BaseException:
        processing_failed = True
        raise
    finally:
        capture.release()
        video_writer.release()
        if processing_failed:
            video_path.unlink(missing_ok=True)

    trajectory_csv = root / "{}_tracks.csv".format(source.stem)
    fields = [
        "frame_index", "time_seconds", "track_id", "class_id", "confidence",
        "center_x", "center_y", "width", "height",
    ]
    with trajectory_csv.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    alert_csv = root / "{}_health_alerts.csv".format(source.stem)
    health_summary_csv = root / "{}_health_summary.csv".format(source.stem)
    health_report_html = root / "{}_health_report.html".format(source.stem)
    monitor.export_alerts_csv(str(alert_csv))
    monitor.export_health_summary_csv(str(health_summary_csv))
    monitor.export_alerts_html(str(health_report_html))

    behavior_csv = root / "{}_behavior.csv".format(source.stem)
    behavior_summary_csv = root / "{}_behavior_summary.csv".format(source.stem)
    behavior_report_json = root / "{}_behavior_report.json".format(source.stem)
    summary = build_behavior_summary(behavior_rows, fps)
    write_behavior_timeline(behavior_csv, behavior_rows)
    write_behavior_summary(behavior_summary_csv, summary)
    write_behavior_report(
        behavior_report_json,
        behavior_rows,
        summary,
        behavior_status,
        behavior_version,
        fps,
        behavior_error,
        decode_error_count=decode_error_count,
    )
    return TrackingVideoResult(
        video_path=video_path,
        trajectory_csv=trajectory_csv,
        alert_csv=alert_csv,
        health_summary_csv=health_summary_csv,
        health_report_html=health_report_html,
        frame_count=frame_index,
        tracked_cattle=len(track_ids_seen),
        alert_count=len(monitor.alerts),
        behavior_csv=behavior_csv,
        behavior_summary_csv=behavior_summary_csv,
        behavior_report_json=behavior_report_json,
        behavior_model_status=behavior_status,
        behavior_model_version=behavior_version,
        behavior_summary=summary,
        decode_error_count=decode_error_count,
    )

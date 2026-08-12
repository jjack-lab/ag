from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import cv2

from health_monitor import CattleHealthMonitor, DetectionObservation, HealthConfig
from inference_profile import build_track_kwargs


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

    def to_dict(self, media_root: str | Path | None = None) -> dict:
        root = Path(media_root).resolve() if media_root else None

        def display(path: Path) -> str:
            resolved = path.resolve()
            return (
                resolved.relative_to(root).as_posix()
                if root
                else resolved.as_posix()
            )

        return {
            "video_path": display(self.video_path),
            "trajectory_csv": display(self.trajectory_csv),
            "alert_csv": display(self.alert_csv),
            "health_summary_csv": display(self.health_summary_csv),
            "health_report_html": display(self.health_report_html),
            "frame_count": self.frame_count,
            "tracked_cattle": self.tracked_cattle,
            "alert_count": self.alert_count,
        }


def process_tracked_video(
    model,
    source_path: str | Path,
    output_dir: str | Path,
    conf: float,
    iou: float,
    class_id: int = 1,
    tracker: str = "bytetrack.yaml",
    progress_callback=None,
) -> TrackingVideoResult:
    source = Path(source_path)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise ValueError(f"Unable to open video: {source}")

    fps = capture.get(cv2.CAP_PROP_FPS) or 20.0
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = max(0, int(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
    video_path = root / f"{source.stem}_tracked.mp4"
    video_writer = cv2.VideoWriter(
        str(video_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not video_writer.isOpened():
        capture.release()
        raise ValueError(f"Unable to create tracked video: {video_path}")

    monitor = CattleHealthMonitor(HealthConfig(fps=fps, cattle_class_ids={class_id}))
    rows: list[dict] = []
    track_ids_seen: set[int] = set()
    frame_index = 0
    try:
        while True:
            success, frame = capture.read()
            if not success:
                break

            track_kwargs = build_track_kwargs(conf, iou, class_id)
            track_kwargs["tracker"] = tracker
            result = model.track(frame, **track_kwargs)[0]
            observations = []
            if result.boxes.id is not None:
                ids = result.boxes.id.int().cpu().tolist()
                xywh = result.boxes.xywh.cpu().tolist()
                classes = result.boxes.cls.int().cpu().tolist()
                confidences = result.boxes.conf.cpu().tolist()
                for track_id, box, detected_class, confidence in zip(
                    ids, xywh, classes, confidences
                ):
                    x, y, width_box, height_box = map(float, box)
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
                            "width": width_box,
                            "height": height_box,
                        }
                    )
                    observations.append(
                        DetectionObservation(
                            track_id=track_id,
                            class_id=detected_class,
                            confidence=float(confidence),
                            xywh=(x, y, width_box, height_box),
                        )
                    )
            monitor.update(frame_index, observations)
            video_writer.write(result.plot())
            frame_index += 1
            if progress_callback and total_frames:
                progress_callback(min(0.99, frame_index / total_frames))
    finally:
        capture.release()
        video_writer.release()

    trajectory_csv = root / f"{source.stem}_tracks.csv"
    with trajectory_csv.open("w", encoding="utf-8-sig", newline="") as target:
        fieldnames = [
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
        csv_writer = csv.DictWriter(target, fieldnames=fieldnames)
        csv_writer.writeheader()
        csv_writer.writerows(rows)

    alert_csv = root / f"{source.stem}_health_alerts.csv"
    summary_csv = root / f"{source.stem}_health_summary.csv"
    report_html = root / f"{source.stem}_health_report.html"
    monitor.export_alerts_csv(str(alert_csv))
    monitor.export_health_summary_csv(str(summary_csv))
    monitor.export_alerts_html(str(report_html))
    return TrackingVideoResult(
        video_path=video_path,
        trajectory_csv=trajectory_csv,
        alert_csv=alert_csv,
        health_summary_csv=summary_csv,
        health_report_html=report_html,
        frame_count=frame_index,
        tracked_cattle=len(track_ids_seen),
        alert_count=len(monitor.alerts),
    )

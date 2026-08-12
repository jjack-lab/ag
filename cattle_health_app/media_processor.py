from __future__ import annotations

from pathlib import Path

import cv2

from cattle_health_app.media_inference import detect_image
from cattle_health_app.model_registry import resolve_detector_model
from cattle_health_app.tracking_pipeline import process_tracked_video
from cattle_health_app.yolo_runtime import load_delivery_yolo_class


YOLO = load_delivery_yolo_class()


class LocalMediaProcessor:
    def __init__(self, model_path: str | Path | None = None):
        self.model_path = resolve_detector_model(explicit_path=model_path).path
        self._model = None

    def detect_image(self, source_path, result_path, conf, iou, class_id):
        result = detect_image(
            self._load_model(), source_path, conf, iou, class_id
        )
        result_path = Path(result_path)
        result_path.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(result_path), result.annotated_frame):
            raise ValueError(f"无法保存识别结果: {result_path}")
        return result.detection_count

    def track_video(
        self,
        source_path,
        result_dir,
        conf,
        iou,
        class_id=1,
        tracker="bytetrack.yaml",
    ):
        return process_tracked_video(
            self._load_model(),
            source_path,
            result_dir,
            conf,
            iou,
            class_id,
            tracker,
        )

    def detect_video(self, source_path, result_dir, conf, iou, class_id):
        return self.track_video(source_path, result_dir, conf, iou, class_id)

    def _load_model(self):
        if self._model is None:
            self._model = YOLO(str(self.model_path))
        return self._model

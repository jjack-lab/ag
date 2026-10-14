from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from threading import Lock

import torch

from cattle_health_app.behavior.runtime import BehaviorRuntime, TorchBehaviorClassifier
from cattle_health_app.behavior.calibration import (
    default_calibration_path,
    load_behavior_calibration,
)
from cattle_health_app.media_inference import detect_image
from cattle_health_app.image_io import write_cv_image
from cattle_health_app.model_registry import (
    resolve_behavior_model,
    resolve_detector_model,
)
from cattle_health_app.tracking_pipeline import process_tracked_video
from cattle_health_app.yolo_runtime import load_delivery_yolo_class


YOLO = load_delivery_yolo_class()


def _build_behavior_runtime(path: Path):
    preferred = "cuda" if torch.cuda.is_available() else "cpu"
    try:
        classifier = TorchBehaviorClassifier.from_checkpoint(path, device=preferred)
    except (RuntimeError, ValueError):
        if preferred == "cpu":
            raise
        classifier = TorchBehaviorClassifier.from_checkpoint(path, device="cpu", amp=False)
    calibration_path = default_calibration_path(path)
    if not calibration_path.is_file():
        if os.environ.get("AGRINEBULA_BEHAVIOR_CALIBRATION"):
            raise FileNotFoundError(
                f"configured behavior calibration is missing: {calibration_path}"
            )
        return BehaviorRuntime(classifier)
    calibration = load_behavior_calibration(
        calibration_path,
        checkpoint_path=path,
        model_version=classifier.model_version,
    )
    classifier.temperature = calibration.temperature
    return BehaviorRuntime(
        classifier,
        confidence_threshold=calibration.min_confidence,
        max_normalized_entropy=calibration.max_normalized_entropy,
    )


class LocalMediaProcessor:
    def __init__(
        self,
        model_path: str | Path | None = None,
        behavior_model_path: str | Path | None = None,
        behavior_runtime_factory=None,
    ):
        self.model_path = resolve_detector_model(explicit_path=model_path).path
        self.behavior_artifact = resolve_behavior_model(
            explicit_path=behavior_model_path
        )
        self._behavior_runtime_factory = (
            behavior_runtime_factory or _build_behavior_runtime
        )
        self._behavior_runtime = None
        self._behavior_runtime_loaded = False
        self._model = None
        self._inference_lock = Lock()

    def detect_image(self, source_path, result_path, conf, iou, class_id):
        with self._inference_lock:
            result = detect_image(
                self._load_model(), source_path, conf, iou, class_id
            )
        result_path = Path(result_path)
        try:
            write_cv_image(result_path, result.annotated_frame)
        except (OSError, ValueError) as exc:
            raise ValueError(f"无法保存识别结果: {result_path}") from exc
        return result.detection_count

    def track_video(
        self,
        source_path,
        result_dir,
        conf,
        iou,
        class_id=1,
        tracker="bytetrack.yaml",
        progress_callback=None,
    ):
        with self._inference_lock:
            return process_tracked_video(
                self._load_model(),
                source_path,
                result_dir,
                conf,
                iou,
                class_id,
                tracker,
                progress_callback=progress_callback,
                behavior_runtime=self._behavior_runtime_for_video() if class_id == 1 else None,
            )

    def detect_video(self, source_path, result_dir, conf, iou, class_id):
        return self.track_video(source_path, result_dir, conf, iou, class_id)

    def _load_model(self):
        if self._model is None:
            self._model = YOLO(str(self.model_path))
        return self._model

    def _load_behavior_runtime(self):
        if self._behavior_runtime_loaded:
            return self._behavior_runtime
        self._behavior_runtime_loaded = True
        if self.behavior_artifact.status != "ready":
            return None
        try:
            runtime = self._behavior_runtime_factory(self.behavior_artifact.path)
        except Exception as error:
            self.behavior_artifact = replace(
                self.behavior_artifact,
                status="failed",
                version=None,
                error="{}: {}".format(type(error).__name__, error),
            )
            return None
        self._behavior_runtime = runtime
        self.behavior_artifact = replace(
            self.behavior_artifact,
            status="ready",
            version=getattr(runtime, "model_version", None),
            error=None,
        )
        return runtime

    def _behavior_runtime_for_video(self):
        runtime = self._load_behavior_runtime()
        if runtime is None:
            return None
        reset = getattr(runtime, "reset", None)
        if not callable(reset):
            return runtime
        try:
            reset()
        except Exception as error:
            self.behavior_artifact = replace(
                self.behavior_artifact,
                status="failed",
                version=None,
                error="{}: {}".format(type(error).__name__, error),
            )
            return None
        return runtime

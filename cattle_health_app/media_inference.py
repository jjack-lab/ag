from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from inference_profile import build_predict_kwargs


@dataclass(frozen=True)
class ImageDetectionResult:
    annotated_frame: np.ndarray
    detection_count: int


def detect_image(model, image_path, conf, iou, class_id=-1):
    results = model.predict(
        str(image_path),
        save=False,
        **build_predict_kwargs(conf, iou, class_id, "image"),
    )
    result = results[0]
    return ImageDetectionResult(
        annotated_frame=result.plot(),
        detection_count=len(result.boxes),
    )


def process_video(model, source_path, output_dir, conf, iou, class_id=-1):
    source_path = Path(source_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{source_path.stem}_detected.mp4"

    capture = cv2.VideoCapture(str(source_path))
    if not capture.isOpened():
        raise ValueError(f"无法打开视频: {source_path}")

    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = capture.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 20.0

    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        capture.release()
        raise ValueError(f"无法创建结果视频: {output_path}")

    try:
        while True:
            success, frame = capture.read()
            if not success:
                break
            results = model.predict(
                frame,
                **build_predict_kwargs(conf, iou, class_id, "video"),
            )
            writer.write(results[0].plot())
    finally:
        capture.release()
        writer.release()

    return output_path

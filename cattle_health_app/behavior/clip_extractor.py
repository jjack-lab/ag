from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from cattle_health_app.behavior.tracks import (
    TrackObservation,
    interpolate_track,
)


class ClipRejected(ValueError):
    pass


@dataclass(frozen=True)
class ClipConfig:
    window_seconds: float = 4.0
    stride_seconds: float = 2.0
    target_fps: float = 12.0
    output_size: int = 224
    bbox_margin: float = 0.15
    minimum_observed_ratio: float = 0.80
    maximum_interpolated_gap: int = 5
    minimum_mean_confidence: float = 0.25


@dataclass(frozen=True)
class ExtractedClip:
    frame_count: int
    observed_ratio: float
    mean_tracking_confidence: float


def expand_and_clamp(
    center_x,
    center_y,
    width,
    height,
    frame_width,
    frame_height,
    margin,
):
    expanded_width = width * (1 + 2 * margin)
    expanded_height = height * (1 + 2 * margin)
    x1 = max(0, int(round(center_x - expanded_width / 2)))
    y1 = max(0, int(round(center_y - expanded_height / 2)))
    x2 = min(frame_width, int(round(center_x + expanded_width / 2)))
    y2 = min(frame_height, int(round(center_y + expanded_height / 2)))
    if x2 <= x1 or y2 <= y1:
        raise ClipRejected("invalid_crop_geometry")
    return x1, y1, x2, y2


def _letterbox(image: np.ndarray, size: int) -> np.ndarray:
    height, width = image.shape[:2]
    scale = min(size / width, size / height)
    resized_width = max(1, int(round(width * scale)))
    resized_height = max(1, int(round(height * scale)))
    resized = cv2.resize(image, (resized_width, resized_height))
    canvas = np.zeros((size, size, 3), dtype=np.uint8)
    x = (size - resized_width) // 2
    y = (size - resized_height) // 2
    canvas[y : y + resized_height, x : x + resized_width] = resized
    return canvas


def _validate_output(
    path: Path,
    config: ClipConfig,
    expected_frames: int,
):
    capture = cv2.VideoCapture(str(path))
    valid = (
        capture.isOpened()
        and int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)) == config.output_size
        and int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)) == config.output_size
        and int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) == expected_frames
    )
    capture.release()
    if not valid:
        path.unlink(missing_ok=True)
        raise ClipRejected("output_integrity")


def extract_clip(
    video_path: str | Path,
    observations: list[TrackObservation],
    track_id: int,
    start_second: float,
    end_second: float,
    output_path: str | Path,
    config: ClipConfig,
) -> ExtractedClip:
    source = Path(video_path)
    output = Path(output_path)
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise ClipRejected(f"video_decode:{source}")
    source_fps = capture.get(cv2.CAP_PROP_FPS)
    frame_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if source_fps <= 0 or frame_width <= 0 or frame_height <= 0:
        capture.release()
        raise ClipRejected("invalid_video_metadata")

    start_frame = int(round(start_second * source_fps))
    end_frame = int(round(end_second * source_fps))
    selected = [
        item
        for item in observations
        if item.track_id == track_id
        and start_frame <= item.frame_index < end_frame
    ]
    expected_source_frames = max(1, end_frame - start_frame)
    observed_ratio = (
        len({item.frame_index for item in selected}) / expected_source_frames
    )
    if observed_ratio < config.minimum_observed_ratio:
        capture.release()
        raise ClipRejected(f"observation_coverage:{observed_ratio:.3f}")
    mean_confidence = sum(item.confidence for item in selected) / len(selected)
    if mean_confidence < config.minimum_mean_confidence:
        capture.release()
        raise ClipRejected(f"tracking_confidence:{mean_confidence:.3f}")

    track = interpolate_track(
        observations,
        track_id,
        start_frame,
        end_frame,
        config.maximum_interpolated_gap,
    )
    output_frames = int(
        round((end_second - start_second) * config.target_fps)
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(output),
        cv2.VideoWriter_fourcc(*"mp4v"),
        config.target_fps,
        (config.output_size, config.output_size),
    )
    if not writer.isOpened():
        capture.release()
        raise ClipRejected(f"output_writer:{output}")

    written = 0
    try:
        for output_index in range(output_frames):
            source_frame = start_frame + int(
                round(output_index * source_fps / config.target_fps)
            )
            source_frame = min(source_frame, end_frame - 1)
            observation = track.get(source_frame)
            if observation is None:
                raise ClipRejected(
                    f"missing_box_after_interpolation:{source_frame}"
                )
            capture.set(cv2.CAP_PROP_POS_FRAMES, source_frame)
            success, frame = capture.read()
            if not success:
                raise ClipRejected(f"video_decode_frame:{source_frame}")
            x1, y1, x2, y2 = expand_and_clamp(
                observation.center_x,
                observation.center_y,
                observation.width,
                observation.height,
                frame_width,
                frame_height,
                config.bbox_margin,
            )
            writer.write(
                _letterbox(frame[y1:y2, x1:x2], config.output_size)
            )
            written += 1
    except Exception:
        writer.release()
        capture.release()
        output.unlink(missing_ok=True)
        raise
    writer.release()
    capture.release()
    _validate_output(output, config, output_frames)
    return ExtractedClip(
        frame_count=written,
        observed_ratio=observed_ratio,
        mean_tracking_confidence=mean_confidence,
    )

from pathlib import Path

import cv2
import numpy as np
import pytest

from cattle_health_app.behavior.clip_extractor import (
    ClipConfig,
    ClipRejected,
    expand_and_clamp,
    extract_clip,
)
from cattle_health_app.behavior.tracks import TrackObservation


def observation(frame, confidence=0.9):
    return TrackObservation(
        frame_index=frame,
        time_seconds=frame / 10,
        track_id=5,
        confidence=confidence,
        center_x=32,
        center_y=32,
        width=24,
        height=20,
    )


def make_video(path: Path, frame_count=40, fps=10):
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"MJPG"),
        fps,
        (64, 64),
    )
    assert writer.isOpened()
    for frame_index in range(frame_count):
        frame = np.zeros((64, 64, 3), dtype=np.uint8)
        frame[22:42, 20:44] = (0, 180, 0)
        cv2.putText(
            frame,
            str(frame_index),
            (2, 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.3,
            (255, 255, 255),
        )
        writer.write(frame)
    writer.release()


def test_expand_and_clamp_never_leaves_frame():
    box = expand_and_clamp(
        center_x=4,
        center_y=5,
        width=20,
        height=20,
        frame_width=64,
        frame_height=64,
        margin=0.15,
    )
    assert box[0] == 0
    assert box[1] == 0
    assert box[2] <= 64
    assert box[3] <= 64


def test_extract_clip_writes_fixed_format_video(tmp_path):
    source = tmp_path / "source.avi"
    output = tmp_path / "clip.mp4"
    make_video(source)
    observations = [observation(frame) for frame in range(40)]

    result = extract_clip(
        source,
        observations,
        track_id=5,
        start_second=0,
        end_second=4,
        output_path=output,
        config=ClipConfig(),
    )

    capture = cv2.VideoCapture(str(output))
    assert capture.isOpened()
    assert int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)) == 224
    assert int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)) == 224
    assert int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) == 48
    assert capture.get(cv2.CAP_PROP_FPS) == pytest.approx(12)
    capture.release()
    assert result.frame_count == 48
    assert result.observed_ratio == pytest.approx(1.0)


def test_extract_clip_rejects_low_track_coverage(tmp_path):
    source = tmp_path / "source.avi"
    make_video(source)

    with pytest.raises(ClipRejected, match="observation_coverage"):
        extract_clip(
            source,
            [observation(frame) for frame in range(10)],
            track_id=5,
            start_second=0,
            end_second=4,
            output_path=tmp_path / "rejected.mp4",
            config=ClipConfig(),
        )

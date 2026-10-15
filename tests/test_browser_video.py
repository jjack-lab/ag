from pathlib import Path

import cv2
import numpy as np
import pytest

from cattle_health_app.browser_video import ensure_browser_playable, ffmpeg_binary


def test_transcode_tracked_video_to_h264_without_losing_frames(tmp_path):
    if ffmpeg_binary() is None:
        pytest.skip("FFmpeg unavailable")
    source = tmp_path / "tracked.mp4"
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"mp4v"), 5, (64, 48))
    assert writer.isOpened()
    for index in range(5):
        writer.write(np.full((48, 64, 3), index * 30, dtype=np.uint8))
    writer.release()

    assert ensure_browser_playable(source)
    assert b"avc1" in source.read_bytes()
    capture = cv2.VideoCapture(str(source))
    assert capture.isOpened()
    assert capture.get(cv2.CAP_PROP_FRAME_COUNT) == 5
    capture.release()


def test_missing_encoder_preserves_original_video(tmp_path, monkeypatch):
    source = tmp_path / "tracked.mp4"
    source.write_bytes(b"original mp4v video")
    monkeypatch.setattr("cattle_health_app.browser_video.ffmpeg_binary", lambda: None)

    assert not ensure_browser_playable(source)
    assert source.read_bytes() == b"original mp4v video"

import numpy as np
import pytest

import cattle_health_app.tracking_pipeline as pipeline
from delivery_tests.test_task8_spec_fixes import (
    DynamicModel,
    SequenceCapture,
    install,
)


def test_cjk_overlay_changes_real_pixels_when_a_cjk_font_is_available():
    font_path = pipeline._discover_cjk_font()
    if font_path is None:
        pytest.skip("No CJK font is installed on this test host")
    pipeline._get_cjk_font.cache_clear()
    frame = np.zeros((80, 320, 3), dtype=np.uint8)
    pipeline._draw_statuses(
        frame,
        [((8, 12), "ID 1 采食 80%", "ID 1 grazing 80%")],
    )
    assert np.count_nonzero(frame[8:50, 4:240]) > 20


def test_missing_cjk_font_uses_stable_ascii_fallback(monkeypatch):
    calls = []
    monkeypatch.setattr(pipeline, "_get_cjk_font", lambda size=20: None)
    monkeypatch.setattr(
        pipeline.cv2,
        "putText",
        lambda frame, text, *args: calls.append(text) or frame,
    )
    frame = np.zeros((60, 240, 3), dtype=np.uint8)
    pipeline._draw_statuses(
        frame,
        [((5, 12), "ID 7 采食 80%", "ID 7 grazing 80%")],
    )
    assert calls == ["ID 7 grazing 80%"]
    calls[0].encode("ascii")


def test_unknown_frame_count_retries_false_then_recovers_one_frame(tmp_path, monkeypatch):
    class UnknownTransient(SequenceCapture):
        sequence = (False, True, False, False, False)
        total = 0
    install(monkeypatch, UnknownTransient)
    monkeypatch.setattr(pipeline, "_draw_statuses", lambda *args: None)
    result = pipeline.process_tracked_video(
        DynamicModel(), tmp_path / "in.mp4", tmp_path / "out", .2, .5
    )
    assert result.frame_count == 1
    assert result.decode_error_count == 1


def test_unknown_frame_count_requires_bounded_failures_before_eof():
    class UnknownEmpty(SequenceCapture):
        sequence = (False, False, False)
        total = 0
    capture = UnknownEmpty("unused")
    frame, errors, eof = pipeline._read_frame(capture, 0)
    assert frame is None and eof is True
    assert errors == 0
    assert not capture.items

import csv
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import cattle_health_app.tracking_pipeline as pipeline
from delivery_tests.test_tracking_behavior_integration import Monitor, Values, Writer


class DynamicBoxes:
    def __init__(self, ids, boxes):
        self.id = Values(ids)
        self.xywh = Values(boxes)
        self.cls = Values([1] * len(ids))
        self.conf = Values([.9] * len(ids))


class DynamicModel:
    def __init__(self, ids=(7,), boxes=((2.0, 2.0, 3.0, 3.0),)):
        self.ids, self.boxes = list(ids), [list(box) for box in boxes]
    def track(self, frame, **kwargs):
        result = SimpleNamespace(boxes=DynamicBoxes(self.ids, self.boxes), plot=lambda: frame.copy())
        return [result]


class SequenceCapture:
    sequence = (True, False)
    total = 1
    shape = (100, 100, 3)
    def __init__(self, _): self.items = list(self.sequence); self.position = 0; self.released = False
    def isOpened(self): return True
    def get(self, key):
        if key == pipeline.cv2.CAP_PROP_FPS: return 20.0
        if key == pipeline.cv2.CAP_PROP_FRAME_WIDTH: return self.shape[1]
        if key == pipeline.cv2.CAP_PROP_FRAME_HEIGHT: return self.shape[0]
        if key == pipeline.cv2.CAP_PROP_FRAME_COUNT: return self.total
        if key == pipeline.cv2.CAP_PROP_POS_FRAMES: return self.position
        return 0
    def read(self):
        success = self.items.pop(0) if self.items else False
        if success:
            self.position += 1
            return True, np.zeros(self.shape, dtype=np.uint8)
        return False, None
    def release(self): self.released = True


def install(monkeypatch, capture=SequenceCapture, writer=Writer):
    monkeypatch.setattr(pipeline.cv2, "VideoCapture", capture)
    monkeypatch.setattr(pipeline.cv2, "VideoWriter", writer)
    monkeypatch.setattr(pipeline.cv2, "VideoWriter_fourcc", lambda *args: 0)
    monkeypatch.setattr(pipeline, "CattleHealthMonitor", Monitor)


class PendingRuntime:
    model_version = "v1"
    confidence_threshold = .45
    def observe_batch(self, values): return []


def prediction(track_id, label_id=2, confidence=.8):
    return SimpleNamespace(track_id=track_id, frame_index=0, timestamp_seconds=0.0,
                           label_id=label_id, label="grazing", display_name="采食",
                           confidence=confidence, health_eligible=True, model_version="v1")


def timeline(result):
    return list(csv.DictReader(result.behavior_csv.open(encoding="utf-8-sig")))


def test_short_clip_and_buffering_frames_record_uncertain_observation(tmp_path, monkeypatch):
    install(monkeypatch)
    monkeypatch.setattr(pipeline.cv2, "putText", lambda *args: args[0])
    result = pipeline.process_tracked_video(DynamicModel(), tmp_path / "in.mp4", tmp_path / "out", .2, .5, behavior_runtime=PendingRuntime())
    assert timeline(result)[0]["display_name"] == "无法确定"
    assert result.behavior_summary == [{"track_id": 7, "label_id": 1, "label": "none", "display_name": "无法确定", "duration_seconds": .05, "percentage": 100.0, "mean_confidence": 0.0, "health_eligible": False, "model_version": "v1"}]


def test_invalid_crop_still_records_uncertain_and_never_calls_runtime(tmp_path, monkeypatch):
    install(monkeypatch)
    monkeypatch.setattr(pipeline.cv2, "putText", lambda *args: args[0])
    class MustNotRun(PendingRuntime):
        def observe_batch(self, values): pytest.fail("invalid crop must not reach runtime")
    result = pipeline.process_tracked_video(DynamicModel(boxes=((2, 2, 0, 3),)), tmp_path / "in.mp4", tmp_path / "out", .2, .5, behavior_runtime=MustNotRun())
    assert timeline(result)[0]["label"] == "none"


def test_mixed_ready_pending_records_each_track_and_draws_at_bbox_anchors(tmp_path, monkeypatch):
    install(monkeypatch)
    calls = []
    monkeypatch.setattr(pipeline.cv2, "putText", lambda frame, text, point, *args: calls.append((text, point)) or frame)
    class Mixed(PendingRuntime):
        def observe_batch(self, values): return [prediction(1)]
    model = DynamicModel(ids=(1, 2), boxes=((20, 30, 10, 10), (70, 80, 20, 10)))
    result = pipeline.process_tracked_video(model, tmp_path / "in.mp4", tmp_path / "out", .2, .5, behavior_runtime=Mixed())
    rows = timeline(result)
    assert {(row["track_id"], row["display_name"]) for row in rows} == {("1", "采食"), ("2", "无法确定")}
    assert calls[0][1] == (13, 17)
    assert calls[1][1] == (57, 67)
    assert "ID 1" in calls[0][0] and "采食" in calls[0][0] and "80%" in calls[0][0]
    assert "ID 2" in calls[1][0] and "待识别" in calls[1][0] and "无法确定" in calls[1][0]


def test_low_confidence_prediction_is_uncertain_in_timeline(tmp_path, monkeypatch):
    install(monkeypatch)
    monkeypatch.setattr(pipeline.cv2, "putText", lambda *args: args[0])
    class Low(PendingRuntime):
        def observe_batch(self, values): return [prediction(7, confidence=.2)]
    result = pipeline.process_tracked_video(DynamicModel(), tmp_path / "in.mp4", tmp_path / "out", .2, .5, behavior_runtime=Low())
    row = timeline(result)[0]
    assert row["label"] == "none" and row["health_eligible"] == "False"


def test_normal_eof_is_not_a_decode_error_and_report_schema_is_versioned(tmp_path, monkeypatch):
    install(monkeypatch)
    monkeypatch.setattr(pipeline.cv2, "putText", lambda *args: args[0])
    result = pipeline.process_tracked_video(DynamicModel(), tmp_path / "in.mp4", tmp_path / "out", .2, .5)
    assert result.decode_error_count == 0
    payload = json.loads(result.behavior_report_json.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    assert "mean_confidence" in payload["summary_fields"]
    assert payload["decode_error_count"] == 0


def test_transient_decode_failure_is_retried_and_recorded(tmp_path, monkeypatch):
    class Transient(SequenceCapture): sequence = (False, True, False)
    install(monkeypatch, Transient)
    monkeypatch.setattr(pipeline.cv2, "putText", lambda *args: args[0])
    result = pipeline.process_tracked_video(DynamicModel(), tmp_path / "in.mp4", tmp_path / "out", .2, .5)
    assert result.frame_count == 1 and result.decode_error_count == 1


def test_midstream_decode_failure_cleans_video_and_does_not_publish_normal_artifacts(tmp_path, monkeypatch):
    class Broken(SequenceCapture): sequence = (True, False, False, False); total = 3
    class FileWriter(Writer):
        def __init__(self, path, *args): super().__init__(); Path(path).write_bytes(b"partial")
    install(monkeypatch, Broken, FileWriter)
    monkeypatch.setattr(pipeline.cv2, "putText", lambda *args: args[0])
    output = tmp_path / "out"
    with pytest.raises(RuntimeError, match="decode.*3"):
        pipeline.process_tracked_video(DynamicModel(), tmp_path / "in.mp4", output, .2, .5)
    assert not (output / "in_tracked.mp4").exists()
    assert not (output / "in_behavior_report.json").exists()

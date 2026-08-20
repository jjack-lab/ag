from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import cattle_health_app.tracking_pipeline as pipeline


class Values:
    def __init__(self, value): self.value = value
    def int(self): return self
    def cpu(self): return self
    def tolist(self): return self.value


class Boxes:
    id = Values([7])
    xywh = Values([[2.0, 2.0, 3.0, 3.0]])
    cls = Values([1])
    conf = Values([.9])


class Result:
    boxes = Boxes()
    def __init__(self, frame): self.frame = frame
    def plot(self): return self.frame.copy()


class Model:
    def track(self, frame, **kwargs): return [Result(frame)]


class Capture:
    def __init__(self, _): self.frames = [np.zeros((6, 8, 3), dtype=np.uint8)]; self.released = False; self.position = 0
    def isOpened(self): return True
    def get(self, key): return self.position if key == 1 else {5: 20.0, 3: 8, 4: 6, 7: 1}.get(key, 0)
    def read(self):
        if not self.frames: return False, None
        self.position += 1
        return True, self.frames.pop(0)
    def release(self): self.released = True


class Writer:
    def __init__(self, *args): self.frames = []; self.released = False
    def isOpened(self): return True
    def write(self, frame): self.frames.append(frame)
    def release(self): self.released = True


class Monitor:
    alerts = ()
    def __init__(self, *_): pass
    def update(self, *_): pass
    def export_alerts_csv(self, path): Path(path).write_text("", encoding="utf-8")
    def export_health_summary_csv(self, path): Path(path).write_text("", encoding="utf-8")
    def export_alerts_html(self, path): Path(path).write_text("", encoding="utf-8")


def install_video_fakes(monkeypatch, writer=Writer):
    monkeypatch.setattr(pipeline.cv2, "VideoCapture", Capture)
    monkeypatch.setattr(pipeline.cv2, "VideoWriter", writer)
    monkeypatch.setattr(pipeline.cv2, "VideoWriter_fourcc", lambda *args: 0)
    monkeypatch.setattr(pipeline.cv2, "putText", lambda *args: args[0])
    monkeypatch.setattr(pipeline, "CattleHealthMonitor", Monitor)


class Runtime:
    model_version = "cvb-v1"
    def observe_batch(self, values):
        assert len(values) == 1
        track, frame, crop, timestamp = values[0]
        assert track == 7 and frame == 0 and crop.size and timestamp == 0
        return [SimpleNamespace(track_id=7, frame_index=0, timestamp_seconds=0.0, label_id=2,
                                label="grazing", display_name="采食", confidence=.8,
                                health_eligible=True, model_version=self.model_version)]


def test_tracking_associates_predictions_and_publishes_behavior_artifacts(tmp_path, monkeypatch):
    install_video_fakes(monkeypatch)
    result = pipeline.process_tracked_video(Model(), tmp_path / "in.mp4", tmp_path / "out", .2, .5, behavior_runtime=Runtime())
    assert result.behavior_model_status == "ready"
    assert result.behavior_summary[0]["track_id"] == 7
    assert result.behavior_summary[0]["display_name"] == "采食"
    assert result.behavior_csv.is_file() and result.behavior_report_json.is_file()


def test_no_runtime_and_failed_runtime_are_explicit_without_fabricated_predictions(tmp_path, monkeypatch):
    install_video_fakes(monkeypatch)
    unavailable = pipeline.process_tracked_video(Model(), tmp_path / "a.mp4", tmp_path / "a", .2, .5)
    assert unavailable.behavior_model_status == "unavailable"
    assert unavailable.behavior_summary == []
    assert unavailable.behavior_csv is None
    assert unavailable.behavior_report_json is None
    class Broken(Runtime):
        def observe_batch(self, values): raise RuntimeError("bad checkpoint")
    failed = pipeline.process_tracked_video(Model(), tmp_path / "b.mp4", tmp_path / "b", .2, .5, behavior_runtime=Broken())
    assert failed.behavior_model_status == "failed"
    assert failed.behavior_summary[0]["display_name"] == "无法确定"
    assert "bad checkpoint" in failed.behavior_report_json.read_text(encoding="utf-8")


def test_writer_open_failure_removes_partial_video(tmp_path, monkeypatch):
    class BrokenWriter(Writer):
        def __init__(self, path, *args): super().__init__(); Path(path).write_bytes(b"partial"); self.path = Path(path)
        def isOpened(self): return False
    install_video_fakes(monkeypatch, BrokenWriter)
    with pytest.raises(ValueError, match="Unable to create tracked video"):
        pipeline.process_tracked_video(Model(), tmp_path / "in.mp4", tmp_path / "out", .2, .5)
    assert not (tmp_path / "out" / "in_tracked.mp4").exists()

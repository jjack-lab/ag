from types import SimpleNamespace

import cattle_health_app.tracking_pipeline as pipeline
from delivery_tests.test_tracking_behavior_integration import Model, Runtime, install_video_fakes


def test_behavior_buffering_draws_explicit_pending_status(tmp_path, monkeypatch):
    install_video_fakes(monkeypatch)
    monkeypatch.setattr(pipeline, "_get_cjk_font", lambda size=20: None)
    drawn = []
    monkeypatch.setattr(pipeline.cv2, "putText", lambda frame, text, *args: drawn.append(text) or frame)
    class NotReady(Runtime):
        def observe_batch(self, values): return []
    result = pipeline.process_tracked_video(Model(), tmp_path / "in.mp4", tmp_path / "out", .2, .5, behavior_runtime=NotReady())
    assert result.behavior_model_status == "ready"
    assert result.behavior_summary[0]["display_name"] == "无法确定"
    assert any("Pending/Unknown" in text for text in drawn)

from pathlib import Path

import numpy as np

import cattle_health_app.media_processor as processor_module
import cattle_health_app.tracking_pipeline as pipeline
from cattle_health_app.behavior.reporting import BehaviorObservation, build_behavior_summary
from cattle_health_app.behavior.runtime import BehaviorRuntime
from delivery_tests.test_task8_spec_fixes import (
    DynamicModel,
    PendingRuntime,
    SequenceCapture,
    install,
    prediction,
    timeline,
)


class Classifier:
    model_version = "test-v1"

    def predict(self, clips):
        values = np.zeros((len(clips), 12), dtype=np.float32)
        values[:, 1] = 1.0
        return values


def test_behavior_runtime_reset_clears_all_per_video_track_state():
    runtime = BehaviorRuntime(Classifier(), clip_frames=1, stride=1)
    crop = np.zeros((8, 8, 3), dtype=np.uint8)
    runtime.observe(7, 20, crop, timestamp_seconds=1.0)

    runtime.reset()

    assert runtime.active_track_ids == ()
    assert runtime.observe(7, 0, crop, timestamp_seconds=0.0).track_id == 7


def test_media_processor_resets_cached_runtime_before_each_video(tmp_path, monkeypatch):
    detector = tmp_path / "detector.pt"
    detector.write_bytes(b"detector")
    behavior = tmp_path / "behavior.pt"
    behavior.write_bytes(b"behavior")

    class Runtime:
        model_version = "test-v1"

        def __init__(self):
            self.reset_count = 0

        def reset(self):
            self.reset_count += 1

    runtime = Runtime()
    processor = processor_module.LocalMediaProcessor(
        model_path=detector,
        behavior_model_path=behavior,
        behavior_runtime_factory=lambda path: runtime,
    )
    monkeypatch.setattr(processor, "_load_model", lambda: object())
    received = []
    monkeypatch.setattr(
        processor_module,
        "process_tracked_video",
        lambda *args, **kwargs: received.append(kwargs["behavior_runtime"]),
    )

    processor.track_video("one.mp4", tmp_path / "one", 0.25, 0.45)
    processor.track_video("two.mp4", tmp_path / "two", 0.25, 0.45)

    assert received == [runtime, runtime]
    assert runtime.reset_count == 2


def test_latest_prediction_is_reused_between_inference_strides(tmp_path, monkeypatch):
    class TwoFrames(SequenceCapture):
        sequence = (True, True, False)
        total = 2

    install(monkeypatch, TwoFrames)
    monkeypatch.setattr(pipeline.cv2, "putText", lambda *args: args[0])

    class Strided(PendingRuntime):
        def __init__(self):
            self.calls = 0

        def observe_batch(self, values):
            self.calls += 1
            return [prediction(7)] if self.calls == 1 else []

    result = pipeline.process_tracked_video(
        DynamicModel(), tmp_path / "in.mp4", tmp_path / "out", .2, .5,
        behavior_runtime=Strided(),
    )

    assert [row["display_name"] for row in timeline(result)] == ["采食", "采食"]
    assert result.behavior_summary[0]["duration_seconds"] == .1


def test_unavailable_runtime_does_not_publish_fabricated_behavior_rows(tmp_path, monkeypatch):
    install(monkeypatch)
    monkeypatch.setattr(pipeline.cv2, "putText", lambda *args: args[0])

    result = pipeline.process_tracked_video(
        DynamicModel(), tmp_path / "in.mp4", tmp_path / "out", .2, .5
    )

    assert result.behavior_model_status == "unavailable"
    assert result.behavior_summary == []
    assert result.behavior_csv is None
    assert result.behavior_summary_csv is None
    assert result.behavior_report_json is None


def test_inference_failure_uses_frontend_failed_status(tmp_path, monkeypatch):
    install(monkeypatch)
    monkeypatch.setattr(pipeline.cv2, "putText", lambda *args: args[0])

    class Broken(PendingRuntime):
        def observe_batch(self, values):
            raise RuntimeError("behavior boom")

    result = pipeline.process_tracked_video(
        DynamicModel(), tmp_path / "in.mp4", tmp_path / "out", .2, .5,
        behavior_runtime=Broken(),
    )

    assert result.behavior_model_status == "failed"
    assert "behavior boom" in result.behavior_model_error
    assert result.trajectory_csv.is_file()


def test_behavior_report_failure_preserves_original_video_artifacts(tmp_path, monkeypatch):
    from delivery_tests.test_tracking_behavior_integration import Writer

    class FileWriter(Writer):
        def __init__(self, path, *args):
            super().__init__(path, *args)
            Path(path).write_bytes(b"video")

    install(monkeypatch, writer=FileWriter)
    monkeypatch.setattr(pipeline.cv2, "putText", lambda *args: args[0])
    monkeypatch.setattr(
        pipeline,
        "write_behavior_timeline",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )

    result = pipeline.process_tracked_video(
        DynamicModel(), tmp_path / "in.mp4", tmp_path / "out", .2, .5,
        behavior_runtime=PendingRuntime(),
    )

    assert result.behavior_model_status == "failed"
    assert "disk full" in result.behavior_model_error
    assert result.behavior_csv is None
    assert result.behavior_summary_csv is None
    assert result.behavior_report_json is None
    for artifact in (
        result.video_path,
        result.trajectory_csv,
        result.alert_csv,
        result.health_summary_csv,
        result.health_report_html,
    ):
        assert Path(artifact).exists()


def test_behavior_report_cleanup_failure_is_also_nonblocking(tmp_path, monkeypatch):
    install(monkeypatch)
    monkeypatch.setattr(pipeline.cv2, "putText", lambda *args: args[0])
    monkeypatch.setattr(
        pipeline,
        "write_behavior_timeline",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )
    original_unlink = Path.unlink

    def locked_behavior_file(path, *args, **kwargs):
        if path.name.endswith("_behavior.csv"):
            raise OSError("file locked")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", locked_behavior_file)

    result = pipeline.process_tracked_video(
        DynamicModel(), tmp_path / "in.mp4", tmp_path / "out", .2, .5,
        behavior_runtime=PendingRuntime(),
    )

    assert result.behavior_model_status == "failed"
    assert "disk full" in result.behavior_model_error
    assert "file locked" in result.behavior_model_error
    assert result.trajectory_csv.is_file()


def test_behavior_durations_follow_track_timestamps_and_repeat_last_interval():
    observations = [
        BehaviorObservation(0, 0.0, 7, 2, "grazing", "采食", .8, True, "v1"),
        BehaviorObservation(20, 1.0, 7, 2, "grazing", "采食", .7, True, "v1"),
        BehaviorObservation(60, 3.0, 7, 3, "walking", "行走", .9, True, "v1"),
    ]

    rows = build_behavior_summary(observations, fps=20.0)

    grazing = next(row for row in rows if row["label"] == "grazing")
    walking = next(row for row in rows if row["label"] == "walking")
    assert grazing["duration_seconds"] == 3.0
    assert grazing["percentage"] == 60.0
    assert walking["duration_seconds"] == 2.0
    assert walking["percentage"] == 40.0


def test_single_behavior_observation_has_zero_duration():
    rows = build_behavior_summary(
        [BehaviorObservation(0, 0.0, 7, 2, "grazing", "采食", .8, True, "v1")],
        fps=20.0,
    )

    assert rows[0]["duration_seconds"] == 0.0
    assert rows[0]["percentage"] == 0.0


def test_reused_observation_instance_does_not_collide_duration_keys():
    grazing = BehaviorObservation(
        0, 0.0, 7, 2, "grazing", "采食", .8, True, "v1"
    )
    walking = BehaviorObservation(
        20, 1.0, 7, 3, "walking", "行走", .9, True, "v1"
    )

    rows = build_behavior_summary([grazing, grazing, walking], fps=20.0)

    durations = {
        row["label"]: row["duration_seconds"] for row in rows
    }
    assert durations == {"grazing": 1.0, "walking": 1.0}

import numpy as np
import pytest
import torch

from cattle_health_app.behavior.runtime import (
    BehaviorRuntime,
    TorchBehaviorClassifier,
    TrackClipBuffer,
)


def crop(value=0):
    return np.full((32, 48, 3), value, dtype=np.uint8)


class FakeClassifier:
    model_version = "fake-v1"

    def __init__(self, probabilities=None):
        self.probabilities = probabilities or ([0.01, 0.80] + [0.019] * 10)
        self.batch_sizes = []

    def predict(self, clips):
        self.batch_sizes.append(len(clips))
        return [list(self.probabilities) for _ in clips]


def test_runtime_waits_for_sixteen_frames_and_returns_per_track_result():
    runtime = BehaviorRuntime(FakeClassifier(), clip_frames=16, stride=4)
    for frame_index in range(15):
        assert runtime.observe(7, frame_index, crop()) is None
    result = runtime.observe(7, 15, crop())
    assert result.track_id == 7
    assert result.label_id == 2
    assert result.label == "grazing"
    assert result.display_name == "采食"
    assert result.confidence == pytest.approx(0.80)
    assert result.raw_label_id == 2
    assert result.raw_confidence == pytest.approx(0.80)
    assert result.frame_index == 15
    assert result.timestamp_seconds is None
    assert result.health_eligible is True


def test_runtime_infers_on_stride_and_batches_tracks_ready_on_same_frame():
    classifier = FakeClassifier()
    runtime = BehaviorRuntime(classifier, clip_frames=2, stride=2)
    runtime.observe_batch([(1, 0, crop()), (2, 0, crop())])
    results = runtime.observe_batch([(1, 1, crop()), (2, 1, crop())])
    assert [result.track_id for result in results] == [1, 2]
    assert classifier.batch_sizes == [2]
    assert runtime.observe(1, 2, crop()) is None
    assert runtime.observe(1, 3, crop()) is not None


def test_low_confidence_maps_to_uncertain_but_preserves_raw_result():
    probabilities = [0.05, 0.44] + [0.051] * 10
    result = BehaviorRuntime(FakeClassifier(probabilities), clip_frames=1).observe(
        9, 4, crop(), timestamp_seconds=1.25
    )
    assert result.label_id == 1
    assert result.label == "none"
    assert result.display_name == "无法确定"
    assert result.health_eligible is False
    assert result.raw_label_id == 2
    assert result.raw_label == "grazing"
    assert result.raw_display_name == "采食"
    assert result.smoothed_label_id == 2
    assert result.smoothed_label == "grazing"
    assert result.smoothed_display_name == "采食"
    assert result.smoothed_confidence == pytest.approx(0.44 / sum(probabilities))
    assert result.timestamp_seconds == pytest.approx(1.25)


@pytest.mark.parametrize("label_id", [1, 10, 11])
def test_dataset_uncertain_classes_are_never_health_eligible(label_id):
    probabilities = [0.0] * 12
    probabilities[label_id - 1] = 1.0
    result = BehaviorRuntime(FakeClassifier(probabilities), clip_frames=1).observe(1, 0, crop())
    assert result.label_id == label_id
    assert result.raw_label_id == label_id
    assert result.smoothed_label_id == label_id
    assert result.raw_display_name == "无法确定"
    assert result.smoothed_display_name == "无法确定"
    assert result.display_name == "无法确定"
    assert result.health_eligible is False


def test_hysteresis_does_not_flicker_when_boundary_predictions_alternate():
    classifier = FakeClassifier([0.0, 0.51, 0.49] + [0.0] * 9)
    runtime = BehaviorRuntime(classifier, clip_frames=1, stride=1, alpha=1.0,
                              switch_margin=0.0, switch_confirmations=2)
    assert runtime.observe(3, 0, crop()).label_id == 2
    for frame_index in range(1, 6):
        classifier.probabilities = ([0.0, 0.49, 0.51] + [0.0] * 9 if frame_index % 2
                                    else [0.0, 0.51, 0.49] + [0.0] * 9)
        assert runtime.observe(3, frame_index, crop()).label_id == 2


def test_hysteresis_switches_after_sustained_new_behavior():
    classifier = FakeClassifier([0.0, 0.9, 0.1] + [0.0] * 9)
    runtime = BehaviorRuntime(classifier, clip_frames=1, stride=1, alpha=1.0,
                              switch_margin=0.1, switch_confirmations=2)
    runtime.observe(3, 0, crop())
    classifier.probabilities = [0.0, 0.1, 0.9] + [0.0] * 9
    pending = runtime.observe(3, 1, crop())
    switched = runtime.observe(3, 2, crop())
    assert pending.smoothed_label_id == 3
    assert pending.label_id == 1
    assert pending.display_name == "无法确定"
    assert pending.health_eligible is False
    assert pending.confidence == pytest.approx(0.1)
    assert pending.smoothed_confidence == pytest.approx(0.9)
    assert switched.label_id == 3


def test_hysteresis_state_is_per_track_and_removed_on_expiry():
    classifier = FakeClassifier([0.0, 0.9, 0.1] + [0.0] * 9)
    runtime = BehaviorRuntime(classifier, clip_frames=1, stride=1, alpha=1.0,
                              switch_margin=0.0, switch_confirmations=2, ttl_frames=1)
    runtime.observe_batch([(1, 0, crop()), (2, 0, crop())])
    classifier.probabilities = [0.0, 0.1, 0.9] + [0.0] * 9
    assert runtime.observe(1, 1, crop()).display_name == "无法确定"
    assert runtime.observe(2, 1, crop()).display_name == "无法确定"
    runtime.expire(3)
    assert runtime.active_track_ids == ()
    assert runtime.observe(1, 4, crop()).label_id == 3


def test_ready_tracks_are_chunked_to_max_batch_size_without_reordering():
    class IdentityClassifier:
        model_version = "identity"

        def __init__(self):
            self.batch_sizes = []

        def predict(self, clips):
            self.batch_sizes.append(len(clips))
            rows = []
            for clip in clips:
                row = [0.0] * 12
                row[int(clip[0][0, 0, 0]) - 1] = 1.0
                rows.append(row)
            return rows

    classifier = IdentityClassifier()
    runtime = BehaviorRuntime(classifier, clip_frames=1, max_batch_size=2)
    results = runtime.observe_batch([(i, 0, crop(i)) for i in range(1, 6)])
    assert classifier.batch_sizes == [2, 2, 1]
    assert [result.track_id for result in results] == [1, 2, 3, 4, 5]
    assert [result.raw_label_id for result in results] == [1, 2, 3, 4, 5]


def test_cuda_oom_halves_batch_but_non_oom_is_not_swallowed():
    class OomClassifier(FakeClassifier):
        device = torch.device("cuda")

        def predict(self, clips):
            self.batch_sizes.append(len(clips))
            if len(clips) > 1:
                raise RuntimeError("CUDA out of memory")
            return [self.probabilities]

    oom = OomClassifier()
    results = BehaviorRuntime(oom, clip_frames=1, max_batch_size=4).observe_batch(
        [(i, 0, crop()) for i in range(4)]
    )
    assert len(results) == 4
    assert oom.batch_sizes == [4, 2, 1, 1, 2, 1, 1]

    class BrokenClassifier(FakeClassifier):
        device = torch.device("cuda")

        def predict(self, clips):
            raise RuntimeError("kernel contract broken")

    with pytest.raises(RuntimeError, match="kernel contract broken"):
        BehaviorRuntime(BrokenClassifier(), clip_frames=1).observe(1, 0, crop())


def test_cpu_and_single_clip_cuda_oom_are_explicit():
    class AlwaysOom(FakeClassifier):
        def __init__(self, device):
            super().__init__()
            self.device = torch.device(device)

        def predict(self, clips):
            raise RuntimeError("out of memory")

    with pytest.raises(RuntimeError, match="out of memory"):
        BehaviorRuntime(AlwaysOom("cpu"), clip_frames=1).observe(1, 0, crop())
    with pytest.raises(RuntimeError, match="single clip"):
        BehaviorRuntime(AlwaysOom("cuda"), clip_frames=1).observe(1, 0, crop())


def test_exponential_smoothing_prevents_one_contradiction_from_flipping_label():
    classifier = FakeClassifier([0.0, 0.9, 0.1] + [0.0] * 9)
    runtime = BehaviorRuntime(classifier, clip_frames=1, stride=1, alpha=0.4)
    first = runtime.observe(3, 0, crop())
    classifier.probabilities = [0.0, 0.1, 0.9] + [0.0] * 9
    second = runtime.observe(3, 1, crop())
    assert first.label_id == 2
    assert second.raw_label_id == 3
    assert second.label_id == 2
    assert second.confidence == pytest.approx(0.58)


def test_missing_tracks_expire_and_release_all_state():
    runtime = BehaviorRuntime(FakeClassifier(), clip_frames=1, fps=10, ttl_frames=3)
    runtime.observe(4, 0, crop())
    runtime.expire(3)
    assert runtime.active_track_ids == (4,)
    runtime.expire(4)
    assert runtime.active_track_ids == ()


def test_cache_limit_evicts_oldest_track_and_each_buffer_is_bounded():
    runtime = BehaviorRuntime(FakeClassifier(), clip_frames=3, max_tracks=2)
    runtime.observe(1, 0, crop())
    runtime.observe(2, 1, crop())
    runtime.observe(3, 2, crop())
    assert runtime.active_track_ids == (2, 3)
    for frame_index in range(3, 20):
        runtime.observe(3, frame_index, crop())
    assert runtime.cached_crop_count <= 6


def test_track_buffer_rejects_duplicate_or_out_of_order_frames():
    buffer = TrackClipBuffer(clip_frames=2, stride=1)
    buffer.append(5, crop())
    with pytest.raises(ValueError, match="strictly increasing"):
        buffer.append(5, crop())


def test_classifier_reuses_evaluation_transform_and_returns_cpu_probabilities(monkeypatch):
    calls = []

    def transform(frames, size=224):
        calls.append((len(frames), size))
        return torch.zeros(3, len(frames), size, size)

    monkeypatch.setattr("cattle_health_app.behavior.runtime.evaluation_transform", transform)

    class Model(torch.nn.Module):
        def forward(self, clips):
            logits = torch.zeros((clips.shape[0], 12), device=clips.device)
            logits[:, 1] = 2
            return logits

    classifier = TorchBehaviorClassifier(Model(), device="cpu", model_version="unit-v1")
    output = classifier.predict([[crop() for _ in range(16)]])
    assert calls == [(16, 224)]
    assert output.device.type == "cpu"
    assert output.shape == (1, 12)
    assert output.sum().item() == pytest.approx(1.0)


def test_classifier_validates_probability_shape_from_runtime():
    class BadClassifier:
        def predict(self, clips):
            return [[1.0, 0.0]] * len(clips)

    with pytest.raises(ValueError, match="12 probabilities"):
        BehaviorRuntime(BadClassifier(), clip_frames=1).observe(1, 0, crop())


def test_batch_expiry_excludes_tracks_observed_in_same_mixed_frame_batch():
    runtime = BehaviorRuntime(FakeClassifier(), clip_frames=2, ttl_frames=32)
    runtime.observe(1, 100, crop(1))
    results = runtime.observe_batch([(1, 101, crop(2)), (2, 1000, crop(3))])
    assert [result.track_id for result in results] == [1]
    assert runtime.active_track_ids == (1, 2)
    assert runtime.cached_crop_count == 3


def test_inference_failure_keeps_ready_clip_for_same_frame_retry():
    class FailsOnce(FakeClassifier):
        def __init__(self, message):
            super().__init__()
            self.message = message
            self.calls = 0

        def predict(self, clips):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError(self.message)
            return super().predict(clips)

    for message in ("kernel failed", "CUDA out of memory"):
        classifier = FailsOnce(message)
        if "memory" in message:
            classifier.device = torch.device("cuda")
        runtime = BehaviorRuntime(classifier, clip_frames=1, stride=4)
        with pytest.raises(RuntimeError):
            runtime.observe(1, 7, crop(7))
        retried = runtime.observe(1, 7, crop(7))
        assert retried.track_id == 1
        assert runtime.observe(1, 8, crop(8)) is None


@pytest.mark.parametrize("bad_observation", [
    (1, 11, np.zeros((4, 4, 3), dtype=np.float32)),
    (1, 9, crop()),
])
def test_invalid_later_observation_does_not_mutate_any_track_state(bad_observation):
    runtime = BehaviorRuntime(FakeClassifier(), clip_frames=3, max_tracks=2)
    runtime.observe(1, 10, crop(1), timestamp_seconds=1.0)
    before_ids = runtime.active_track_ids
    before_count = runtime.cached_crop_count
    with pytest.raises(ValueError):
        runtime.observe_batch([(2, 11, crop(2), 1.1), bad_observation])
    assert runtime.active_track_ids == before_ids
    assert runtime.cached_crop_count == before_count
    assert runtime.observe(1, 11, crop(3), timestamp_seconds=1.1) is None


def test_duplicate_late_in_batch_and_bad_timestamp_are_transactional():
    runtime = BehaviorRuntime(FakeClassifier(), clip_frames=3)
    runtime.observe(1, 10, crop())
    for observations in (
        [(2, 11, crop()), (2, 12, crop())],
        [(2, 11, crop(), -0.1)],
    ):
        with pytest.raises(ValueError):
            runtime.observe_batch(observations)
        assert runtime.active_track_ids == (1,)
        assert runtime.cached_crop_count == 1


def test_timestamp_is_nonnegative_and_monotonic_per_track():
    runtime = BehaviorRuntime(FakeClassifier(), clip_frames=3)
    runtime.observe(1, 1, crop(), timestamp_seconds=2.0)
    with pytest.raises(ValueError, match="monotonic"):
        runtime.observe(1, 2, crop(), timestamp_seconds=1.9)
    with pytest.raises(ValueError, match="nonnegative"):
        runtime.observe(2, 2, crop(), timestamp_seconds=-1.0)
    assert runtime.cached_crop_count == 1


def test_amp_requires_an_actual_boolean():
    with pytest.raises(TypeError, match="amp"):
        TorchBehaviorClassifier(torch.nn.Identity(), amp=1)


def test_classifier_rejects_nonfinite_logits():
    class NonFinite(torch.nn.Module):
        def forward(self, clips):
            return torch.full((clips.shape[0], 12), float("nan"))

    classifier = TorchBehaviorClassifier(NonFinite(), device="cpu")
    with pytest.raises(ValueError, match="finite"):
        classifier.predict([[crop() for _ in range(16)]])

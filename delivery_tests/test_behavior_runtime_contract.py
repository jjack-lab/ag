import numpy as np


class FakeClassifier:
    model_version = "contract-v1"

    def predict(self, clips):
        return [[0.0, 1.0] + [0.0] * 10 for _ in clips]


def test_runtime_buffers_tracks_independently_and_returns_product_label():
    from cattle_health_app.behavior.runtime import BehaviorRuntime

    runtime = BehaviorRuntime(FakeClassifier(), clip_frames=2, stride=1)
    crop = np.zeros((24, 32, 3), dtype=np.uint8)

    assert runtime.observe(7, 0, crop) is None
    assert runtime.observe(8, 0, crop) is None
    prediction = runtime.observe(7, 1, crop)

    assert prediction.track_id == 7
    assert prediction.label == "grazing"
    assert prediction.display_name == "采食"
    assert prediction.health_eligible is True
    assert prediction.model_version == "contract-v1"


def test_low_confidence_prediction_is_uncertain():
    from cattle_health_app.behavior.runtime import BehaviorRuntime

    class LowConfidenceClassifier:
        model_version = "contract-v1"

        def predict(self, clips):
            return [[0.05, 0.44] + [0.051] * 10 for _ in clips]

    runtime = BehaviorRuntime(
        LowConfidenceClassifier(), clip_frames=1, confidence_threshold=0.45
    )
    prediction = runtime.observe(
        3, 0, np.zeros((24, 32, 3), dtype=np.uint8)
    )

    assert prediction.display_name == "无法确定"
    assert prediction.health_eligible is False

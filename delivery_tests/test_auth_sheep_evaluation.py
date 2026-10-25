import csv
import json

import numpy as np

from scripts.evaluate_auth_sheep import run_evaluation, score_existing_predictions


class _Array:
    def __init__(self, value):
        self.value = value

    def cpu(self):
        return self

    def tolist(self):
        return self.value


class _Boxes:
    def __init__(self, found):
        self.id = _Array([7]) if found else None
        self.xywh = _Array([[20, 10, 20, 10]] if found else [])
        self.cls = _Array([0] if found else [])
        self.conf = _Array([0.9] if found else [])


class _Model:
    def __init__(self):
        self.calls = 0

    def track(self, frame, **kwargs):
        self.calls += 1
        assert kwargs["classes"] == [0]
        assert kwargs["persist"] is True
        return [type("Result", (), {"boxes": _Boxes(self.calls == 1)})()]


class _Capture:
    def __init__(self):
        self.calls = 0

    def isOpened(self):
        return True

    def get(self, prop):
        return {3: 100, 4: 50, 7: 2}[prop]

    def read(self):
        self.calls += 1
        return (self.calls <= 2, np.zeros((50, 100, 3), dtype=np.uint8))

    def release(self):
        pass


def test_auth_sheep_evaluator_writes_predictions_and_metrics(tmp_path):
    truth = tmp_path / "truth.csv"
    truth.write_text(
        "frame_index,class_id,track_id,x,y,width,height\n"
        "0,0,7,0.1,0.1,0.2,0.2\n"
        "1,0,7,0.1,0.1,0.2,0.2\n",
        encoding="utf-8",
    )
    predictions = tmp_path / "predictions.csv"
    report = tmp_path / "metrics.json"
    model = _Model()

    result = run_evaluation("fake.mp4", truth, model, predictions, report, capture_factory=lambda _: _Capture())

    assert model.calls == 2
    assert result["true_positive"] == 1
    assert result["false_negative"] == 1
    assert result["recall"] == 0.5
    assert json.loads(report.read_text(encoding="utf-8"))["recall"] == 0.5
    with predictions.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 1
    assert rows[0]["frame_index"] == "0"
    rescored = score_existing_predictions(
        "fake.mp4", truth, predictions, report,
        capture_factory=lambda _: _Capture(),
    )
    assert rescored == result

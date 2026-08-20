import pytest


def test_product_behavior_contract_is_available():
    from cattle_health_app.behavior.cvb_labels import (
        CVB_LABELS,
        behavior_display,
        health_eligible,
    )
    from cattle_health_app.behavior.model import INPUT_FRAMES, INPUT_SIZE, LABEL_ORDER

    assert tuple(CVB_LABELS) == tuple(range(1, 13))
    assert LABEL_ORDER[0] == "none"
    assert LABEL_ORDER[-1] == "running"
    assert behavior_display(2) == "采食"
    assert health_eligible(1) is False
    assert health_eligible(8) is True
    assert INPUT_FRAMES == 16
    assert INPUT_SIZE == 224


def test_missing_behavior_checkpoint_is_rejected(tmp_path):
    from cattle_health_app.behavior.model import load_behavior_checkpoint

    with pytest.raises(FileNotFoundError):
        load_behavior_checkpoint(tmp_path / "missing.pt")

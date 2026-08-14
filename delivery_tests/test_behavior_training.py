import pytest, torch
from cattle_health_app.behavior.train import TrainingConfig, compute_metrics, make_class_weights

def test_config_and_weights_and_metrics():
    assert TrainingConfig().epochs == 30
    with pytest.raises(ValueError): TrainingConfig(epochs=0)
    w=make_class_weights(range(1,13)); assert torch.isfinite(w).all() and w[0]>w[-1]
    m=compute_metrics([0,1,1],[0,0,1],2)
    assert m["accuracy"] == pytest.approx(2/3)
    assert len(m["per_class"]) == 2


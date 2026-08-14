import copy
from pathlib import Path

import pytest
import torch
from torch import nn

from cattle_health_app.behavior.cvb_labels import CVB_LABELS
from cattle_health_app.behavior import model as behavior_model


class TinyX3D(nn.Module):
    def __init__(self):
        super().__init__()
        self.backbone = nn.Linear(3, 4)
        self.blocks = nn.ModuleList([nn.Identity() for _ in range(5)] + [nn.Module()])
        self.blocks[5].proj = nn.Linear(4, 400)

    def forward(self, value):
        value = value.mean(dim=(2, 3, 4))
        return self.blocks[5].proj(self.backbone(value))


@pytest.fixture
def tiny_builder(monkeypatch):
    built = TinyX3D()
    calls = {"pretrained": [], "model": built}

    def builder(*, pretrained):
        calls["pretrained"].append(pretrained)
        return built

    monkeypatch.setattr(behavior_model, "_x3d_xs", builder)
    return calls


def test_build_replaces_only_projection_and_forwards_pretrained(tiny_builder):
    original = tiny_builder["model"]
    old_projection = original.blocks[5].proj
    before = {name: value.clone() for name, value in original.state_dict().items()}
    model = behavior_model.build_x3d(12, pretrained=True)
    assert model is original
    assert tiny_builder["pretrained"] == [True]
    assert model.blocks[5].proj is not old_projection
    assert model.blocks[5].proj.weight.data_ptr() != old_projection.weight.data_ptr()
    for name, value in model.state_dict().items():
        if not name.startswith("blocks.5.proj."):
            assert torch.equal(value, before[name]), name
    with torch.inference_mode():
        assert model(torch.zeros(2, 3, 2, 4, 4)).shape == (2, 12)


def test_false_path_is_forwarded_without_download(tiny_builder):
    behavior_model.build_x3d(pretrained=False)
    assert tiny_builder["pretrained"] == [False]


def test_real_x3d_full_input_contract_without_pretrained_download():
    previous = torch.get_num_threads()
    torch.set_num_threads(min(previous, 2))
    try:
        model = behavior_model.build_x3d(12, pretrained=False).eval()
        with torch.inference_mode():
            assert model(torch.zeros(1, 3, 16, 224, 224)).shape == (1, 12)
    finally:
        torch.set_num_threads(previous)


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_num_classes_must_be_positive_integer(value):
    with pytest.raises(ValueError, match="num_classes"):
        behavior_model.build_x3d(value, pretrained=False)


def _save(path, tiny_builder):
    model = behavior_model.build_x3d(pretrained=False)
    behavior_model.save_behavior_checkpoint(
        path, model, {"macro_f1": 0.8}, {"seed": 7}, model_version="trial-2"
    )
    return model


def test_checkpoint_round_trip_preserves_state_and_metadata(tmp_path, tiny_builder):
    path = tmp_path / "nested" / "model.pt"
    source = _save(path, tiny_builder)
    before = copy.deepcopy(source.state_dict())
    loaded = behavior_model.load_behavior_checkpoint(path)
    assert loaded.model.training is False
    assert next(loaded.model.parameters()).device.type == "cpu"
    assert loaded.metadata.model_version == "trial-2"
    assert loaded.metadata.metrics == {"macro_f1": 0.8}
    assert loaded.metadata.training_config == {"seed": 7}
    assert loaded.metadata.labels == tuple(CVB_LABELS[i].name for i in range(1, 13))
    for key, value in before.items():
        assert torch.equal(value, source.state_dict()[key])
        assert torch.equal(value, loaded.model.state_dict()[key])



def test_loaded_metadata_is_recursively_immutable(tmp_path, tiny_builder):
    path = tmp_path / "model.pt"
    model = behavior_model.build_x3d(pretrained=False)
    behavior_model.save_behavior_checkpoint(
        path, model, {"nested": {"items": [1, 2]}}, {"options": [{"x": 1}]}
    )
    metadata = behavior_model.load_behavior_checkpoint(path).metadata
    with pytest.raises(TypeError):
        metadata.metrics["nested"]["new"] = 3
    with pytest.raises(TypeError):
        metadata.metrics["nested"]["items"][0] = 9

    with pytest.raises(TypeError):
        metadata.training_config["options"][0]["x"] = 2

def test_saved_payload_has_exact_schema(tmp_path, tiny_builder):
    path = tmp_path / "model.pt"
    _save(path, tiny_builder)
    payload = torch.load(path, map_location="cpu")
    assert set(payload) == set(behavior_model.CHECKPOINT_FIELDS)
    assert payload["format_version"] == 1
    assert payload["architecture"] == "x3d_xs"
    assert payload["input_frames"] == 16
    assert payload["input_size"] == 224
    assert payload["labels"] == [CVB_LABELS[i].name for i in range(1, 13)]
    assert all(t.device.type == "cpu" for t in payload["state_dict"].values())


@pytest.mark.parametrize(
    "change,match",
    [
        (lambda p: p.pop("architecture"), "fields"),
        (lambda p: p.update(extra=1), "fields"),
        (lambda p: p.update(format_version=2), "format_version"),
        (lambda p: p.update(architecture="r3d"), "architecture"),
        (lambda p: p.update(labels=list(reversed(p["labels"]))), "labels"),
        (lambda p: p.update(input_frames=8), "input_frames"),
        (lambda p: p.update(input_size=112), "input_size"),
        (lambda p: p.update(model_version=""), "model_version"),
        (lambda p: p.update(metrics=[]), "metrics"),
        (lambda p: p.update(training_config=[]), "training_config"),
        (lambda p: p.update(state_dict={}), "state_dict"),
    ],
)
def test_invalid_payload_rejected_before_model_build(tmp_path, tiny_builder, change, match):
    good = tmp_path / "good.pt"
    _save(good, tiny_builder)
    payload = torch.load(good, map_location="cpu")
    change(payload)
    bad = tmp_path / "bad.pt"
    torch.save(payload, bad)
    tiny_builder["pretrained"].clear()
    with pytest.raises(ValueError, match=match):
        behavior_model.load_behavior_checkpoint(bad)
    assert tiny_builder["pretrained"] == []



@pytest.mark.parametrize(
    "bad",
    [
        {"nested": {1: "integer key"}},
        {"nested": {"bad": {1, 2}}},
        {"nested": {"bad": torch.tensor(1)}},
        {"nested": {"bad": object()}},
        {"nested": {"bad": float("nan")}},
        {"nested": {"bad": float("inf")}},
        {"nested": {"bad": float("-inf")}},
    ],
)
def test_save_rejects_invalid_nested_json_metadata(tmp_path, tiny_builder, bad):
    model = behavior_model.build_x3d(pretrained=False)
    with pytest.raises(ValueError, match="JSON-compatible"):
        behavior_model.save_behavior_checkpoint(tmp_path / "bad.pt", model, bad, {})


@pytest.mark.parametrize(
    "bad",
    [{"nested": {1: "bad"}}, {"nested": {"bad": {1}}}, {"nested": {"bad": float("nan")}}],
)
def test_load_rejects_invalid_nested_json_metadata_before_build(tmp_path, tiny_builder, bad):
    path = tmp_path / "good.pt"
    _save(path, tiny_builder)
    payload = torch.load(path, map_location="cpu")
    payload["metrics"] = bad
    torch.save(payload, path)
    tiny_builder["pretrained"].clear()
    with pytest.raises(ValueError, match="JSON-compatible"):
        behavior_model.load_behavior_checkpoint(path)
    assert tiny_builder["pretrained"] == []
@pytest.mark.parametrize("payload", [None, [], "bad"])
def test_non_mapping_payload_rejected(tmp_path, payload):
    path = tmp_path / "bad.pt"
    torch.save(payload, path)
    with pytest.raises(ValueError, match="mapping"):
        behavior_model.load_behavior_checkpoint(path)


def test_bad_state_dict_is_wrapped_as_value_error(tmp_path, tiny_builder):
    path = tmp_path / "model.pt"
    _save(path, tiny_builder)
    payload = torch.load(path, map_location="cpu")
    payload["state_dict"].pop(next(iter(payload["state_dict"])))
    torch.save(payload, path)
    with pytest.raises(ValueError, match="state_dict"):
        behavior_model.load_behavior_checkpoint(path)


def test_missing_directory_and_corrupt_paths_are_clear(tmp_path):
    with pytest.raises(FileNotFoundError):
        behavior_model.load_behavior_checkpoint(tmp_path / "missing.pt")
    with pytest.raises(ValueError, match="regular file"):
        behavior_model.load_behavior_checkpoint(tmp_path)
    bad = tmp_path / "corrupt.pt"
    bad.write_bytes(b"not pickle")
    with pytest.raises(ValueError, match="checkpoint"):
        behavior_model.load_behavior_checkpoint(bad)


def test_failed_replace_preserves_destination_and_cleans_temp(tmp_path, tiny_builder, monkeypatch):
    path = tmp_path / "model.pt"
    path.write_bytes(b"original")
    model = behavior_model.build_x3d(pretrained=False)

    def fail_replace(source, destination):
        raise OSError("injected")

    monkeypatch.setattr(behavior_model.os, "replace", fail_replace)
    with pytest.raises(OSError, match="injected"):
        behavior_model.save_behavior_checkpoint(path, model, {}, {})
    assert path.read_bytes() == b"original"
    assert list(tmp_path.glob(".*.tmp")) == []

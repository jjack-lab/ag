import json
import os
import hashlib
from pathlib import Path

import numpy as np
import pytest
import torch
from types import SimpleNamespace

import cattle_health_app.behavior.uncertainty_experiment as experiment


def prediction_sets():
    validation = experiment.PredictionSet(
        sample_ids=("val-1", "val-2", "val-3", "val-4", "val-5", "val-6"),
        logits=np.log(
            np.array(
                [
                    [0.90, 0.05, 0.05],
                    [0.55, 0.40, 0.05],
                    [0.10, 0.80, 0.10],
                    [0.45, 0.50, 0.05],
                    [0.40, 0.50, 0.10],
                    [0.20, 0.20, 0.60],
                ],
                dtype=np.float64,
            )
        ),
        labels=np.array([0, 0, 1, 1, 0, 2], dtype=np.int64),
    )
    test = experiment.PredictionSet(
        sample_ids=("test-1", "test-2", "test-3", "test-4"),
        logits=np.log(
            np.array(
                [
                    [0.85, 0.10, 0.05],
                    [0.25, 0.65, 0.10],
                    [0.50, 0.40, 0.10],
                    [0.20, 0.20, 0.60],
                ],
                dtype=np.float64,
            )
        ),
        labels=np.array([0, 1, 1, 2], dtype=np.int64),
    )
    return validation, test


def run(tmp_path, output_name="result"):
    validation, test = prediction_sets()
    return experiment.run_experiment(
        validation,
        test,
        tmp_path / output_name,
        checkpoint_sha256="a" * 64,
        validation_manifest_sha256="b" * 64,
        test_manifest_sha256="c" * 64,
        model_version="unit-v1",
        confidence_grid=[0.0, 0.55],
        entropy_grid=[1.0],
        minimum_actionable_coverage=0.60,
        uncertain_label_ids=(2,),
    )


def test_experiment_fits_only_validation_and_freezes_policy_for_test(
    tmp_path, monkeypatch
):
    validation, test = prediction_sets()
    fitted = []
    selected = []
    original_fit = experiment.fit_temperature
    original_select = experiment.select_rejection_policy

    def capture_fit(logits, labels):
        fitted.append((np.array(logits), np.array(labels)))
        return original_fit(logits, labels)

    def capture_select(probabilities, labels, *args, **kwargs):
        selected.append((np.array(probabilities), np.array(labels)))
        return original_select(probabilities, labels, *args, **kwargs)

    monkeypatch.setattr(experiment, "fit_temperature", capture_fit)
    monkeypatch.setattr(experiment, "select_rejection_policy", capture_select)

    result = run(tmp_path)

    assert len(fitted) == 1
    np.testing.assert_array_equal(fitted[0][0], validation.logits)
    np.testing.assert_array_equal(fitted[0][1], validation.labels)
    assert len(selected) == 1
    np.testing.assert_array_equal(selected[0][1], validation.labels)
    assert result["test_sample_count"] == len(test.sample_ids)
    assert result["selection_split"] == "validation"


def test_experiment_writes_traceable_protocol_artifacts(tmp_path):
    result = run(tmp_path)
    output = tmp_path / "result"

    assert sorted(path.name for path in output.iterdir()) == [
        "calibration.json",
        "experiment_metrics.json",
        "protocol_comparison.csv",
        "test_predictions.csv",
    ]
    calibration = json.loads((output / "calibration.json").read_text("utf-8"))
    assert calibration["schema_version"] == 1
    assert calibration["checkpoint_sha256"] == "a" * 64
    assert calibration["validation_manifest_sha256"] == "b" * 64
    assert "test_manifest_sha256" not in calibration
    assert calibration["policy"]["selection_split"] == "validation"
    metrics = json.loads((output / "experiment_metrics.json").read_text("utf-8"))
    assert metrics == result
    assert list(metrics["protocols"]) == [
        "uncalibrated_fixed_045",
        "temperature_fixed_045",
        "temperature_joint_rejection",
    ]
    assert metrics["test_manifest_sha256"] == "c" * 64
    assert "F:\\" not in (output / "experiment_metrics.json").read_text("utf-8")


def test_prediction_set_rejects_duplicate_sample_ids_before_fitting(tmp_path):
    validation, test = prediction_sets()
    duplicate = experiment.PredictionSet(
        sample_ids=("same", "same"),
        logits=validation.logits[:2],
        labels=validation.labels[:2],
    )

    with pytest.raises(ValueError, match="sample IDs"):
        experiment.run_experiment(
            duplicate,
            test,
            tmp_path / "result",
            checkpoint_sha256="a" * 64,
            validation_manifest_sha256="b" * 64,
            test_manifest_sha256="c" * 64,
            model_version="unit-v1",
            uncertain_label_ids=(2,),
        )


def test_core_json_artifacts_are_byte_deterministic(tmp_path):
    run(tmp_path, "first")
    run(tmp_path, "second")

    for name in ("calibration.json", "experiment_metrics.json"):
        assert (tmp_path / "first" / name).read_bytes() == (
            tmp_path / "second" / name
        ).read_bytes()


def test_failed_publish_restores_previous_output(tmp_path, monkeypatch):
    output = tmp_path / "result"
    output.mkdir()
    marker = output / "previous.txt"
    marker.write_text("keep", encoding="utf-8")
    original_replace = os.replace

    def fail_staging_publish(source, destination):
        source_path = Path(source)
        destination_path = Path(destination)
        if ".staging-" in source_path.name and destination_path == output:
            raise OSError("publish failed")
        return original_replace(source, destination)

    monkeypatch.setattr(experiment.os, "replace", fail_staging_publish)

    with pytest.raises(OSError, match="publish failed"):
        run(tmp_path)

    assert marker.read_text("utf-8") == "keep"
    assert not list(tmp_path.glob(".result.staging-*"))
    assert not list(tmp_path.glob(".result.backup-*"))


def test_collect_predictions_preserves_manifest_order_and_raw_logits():
    class Dataset(torch.utils.data.Dataset):
        samples = [
            SimpleNamespace(sample_id="sample-b"),
            SimpleNamespace(sample_id="sample-a"),
            SimpleNamespace(sample_id="sample-c"),
        ]

        def __len__(self):
            return 3

        def __getitem__(self, index):
            logits = torch.tensor(
                [float(index), float(index + 1), float(index + 2)]
            )
            return logits, index % 3

    class IdentityModel(torch.nn.Module):
        def forward(self, values):
            return values

    model = IdentityModel().train()
    predictions = experiment.collect_predictions(
        Dataset(), model, device="cpu", batch_size=2, workers=0
    )

    assert predictions.sample_ids == ("sample-b", "sample-a", "sample-c")
    np.testing.assert_allclose(
        predictions.logits,
        [[0.0, 1.0, 2.0], [1.0, 2.0, 3.0], [2.0, 3.0, 4.0]],
    )
    np.testing.assert_array_equal(predictions.labels, [0, 1, 2])
    assert model.training is False


@pytest.mark.parametrize("batch_size,workers", [(0, 0), (1, -1), (True, 0)])
def test_collect_predictions_validates_loader_settings(batch_size, workers):
    class Dataset(torch.utils.data.Dataset):
        samples = [SimpleNamespace(sample_id="sample")]

        def __len__(self):
            return 1

        def __getitem__(self, index):
            return torch.zeros(3), 0

    with pytest.raises((TypeError, ValueError)):
        experiment.collect_predictions(
            Dataset(), torch.nn.Identity(), "cpu", batch_size, workers
        )


def test_run_from_paths_hashes_inputs_and_keeps_split_roles(tmp_path, monkeypatch):
    index_root = tmp_path / "index"
    index_root.mkdir()
    validation_manifest = index_root / "val.csv"
    test_manifest = index_root / "test.csv"
    checkpoint = tmp_path / "model.pt"
    validation_manifest.write_bytes(b"validation manifest")
    test_manifest.write_bytes(b"test manifest")
    checkpoint.write_bytes(b"checkpoint")
    source_root = tmp_path / "source"
    source_root.mkdir()
    created = []

    class Dataset:
        def __init__(self, manifest, data_root, training, size):
            self.manifest = Path(manifest)
            created.append((self.manifest.name, Path(data_root), training, size))

    monkeypatch.setattr(experiment, "CvbClipDataset", Dataset)
    monkeypatch.setattr(
        experiment,
        "load_behavior_checkpoint",
        lambda path, device: SimpleNamespace(
            model=torch.nn.Identity(),
            metadata=SimpleNamespace(input_size=224, model_version="checkpoint-v1"),
        ),
    )
    validation, test = prediction_sets()
    monkeypatch.setattr(
        experiment,
        "collect_predictions",
        lambda dataset, *args, **kwargs: validation if dataset.manifest.name == "val.csv" else test,
    )
    received = {}

    def capture_run(validation_values, test_values, output_root, **kwargs):
        received.update(kwargs)
        received["validation"] = validation_values
        received["test"] = test_values
        received["output_root"] = Path(output_root)
        return {"status": "captured"}

    monkeypatch.setattr(experiment, "run_experiment", capture_run)

    result = experiment.run_from_paths(
        index_root=index_root,
        source_data_root=source_root,
        checkpoint=checkpoint,
        output_root=tmp_path / "output",
        device="cpu",
        batch_size=2,
        workers=0,
    )

    assert result == {"status": "captured"}
    assert created == [
        ("val.csv", source_root, False, 224),
        ("test.csv", source_root, False, 224),
    ]
    assert received["validation"] is validation
    assert received["test"] is test
    assert received["checkpoint_sha256"] == hashlib.sha256(b"checkpoint").hexdigest()
    assert received["validation_manifest_sha256"] == hashlib.sha256(
        b"validation manifest"
    ).hexdigest()
    assert received["test_manifest_sha256"] == hashlib.sha256(
        b"test manifest"
    ).hexdigest()
    assert received["model_version"] == "checkpoint-v1"


def test_cli_requires_all_data_and_output_paths():
    parser = experiment.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args([])

    args = parser.parse_args(
        [
            "--index-root", "index",
            "--source-data-root", "source",
            "--checkpoint", "model.pt",
            "--output-root", "output",
            "--device", "cpu",
        ]
    )
    assert args.index_root == "index"
    assert args.device == "cpu"


def test_training_wrapper_exposes_uncertainty_mode():
    script = (Path(__file__).parents[1] / "scripts" / "train_cvb_behavior.ps1").read_text(
        encoding="utf-8"
    )

    assert "'smoke','train','evaluate','uncertainty'" in script
    assert "cattle_health_app.behavior.uncertainty_experiment" in script
    assert "--minimum-actionable-coverage" in script

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
    assert calibration["validation_selection"]["selected_sample_count"] == 6
    assert calibration["validation_selection"]["sampling_method"] == "all"
    metrics = json.loads((output / "experiment_metrics.json").read_text("utf-8"))
    assert metrics == result
    assert list(metrics["protocols"]) == [
        "uncalibrated_fixed_045",
        "temperature_fixed_045",
        "temperature_joint_rejection",
    ]
    assert metrics["test_manifest_sha256"] == "c" * 64
    assert metrics["test_selection"]["selected_sample_count"] == 4
    assert len(metrics["test_selection"]["sample_ids_sha256"]) == 64
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


def test_experiment_default_threshold_grids_stay_within_unit_interval(tmp_path):
    validation, test = prediction_sets()

    result = experiment.run_experiment(
        validation,
        test,
        tmp_path / "result",
        checkpoint_sha256="a" * 64,
        validation_manifest_sha256="b" * 64,
        test_manifest_sha256="c" * 64,
        model_version="unit-v1",
        minimum_actionable_coverage=0.60,
        uncertain_label_ids=(2,),
    )

    assert 0.0 <= result["policy"]["max_normalized_entropy"] <= 1.0


def test_prediction_cache_round_trips_and_requires_exact_fingerprint(tmp_path):
    validation, _ = prediction_sets()
    cache = tmp_path / "validation.npz"
    fingerprint = {
        "checkpoint_sha256": "a" * 64,
        "manifest_sha256": "b" * 64,
        "sample_ids_sha256": "c" * 64,
        "model_version": "unit-v1",
    }

    experiment.save_prediction_cache(cache, validation, fingerprint)
    restored = experiment.load_prediction_cache(cache, fingerprint)

    assert restored.sample_ids == validation.sample_ids
    np.testing.assert_array_equal(restored.logits, validation.logits)
    np.testing.assert_array_equal(restored.labels, validation.labels)
    assert experiment.load_prediction_cache(
        cache, {**fingerprint, "model_version": "different"}
    ) is None


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
            self.samples = [SimpleNamespace(sample_id=f"{self.manifest.name}-sample")]
            created.append((self.manifest.name, Path(data_root), training, size))

        def __len__(self):
            return len(self.samples)

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


def test_run_from_paths_applies_split_specific_sampling_before_inference(
    tmp_path, monkeypatch
):
    index_root = tmp_path / "index"
    index_root.mkdir()
    (index_root / "val.csv").write_text("val", encoding="utf-8")
    (index_root / "test.csv").write_text("test", encoding="utf-8")
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"checkpoint")
    source_root = tmp_path / "source"
    source_root.mkdir()

    class Dataset:
        def __init__(self, manifest, *args, **kwargs):
            self.name = Path(manifest).name

    monkeypatch.setattr(experiment, "CvbClipDataset", Dataset)
    monkeypatch.setattr(
        experiment,
        "load_behavior_checkpoint",
        lambda *args, **kwargs: SimpleNamespace(
            model=torch.nn.Identity(),
            metadata=SimpleNamespace(input_size=224, model_version="v1"),
        ),
    )
    sampled = []

    def capture_subset(dataset, max_samples_per_class, seed):
        sampled.append((dataset.name, max_samples_per_class, seed))

        class Sampled:
            name = f"sampled-{dataset.name}"
            samples = [SimpleNamespace(sample_id=f"{name}-sample")]

            def __len__(self):
                return len(self.samples)

        return Sampled()

    monkeypatch.setattr(experiment, "class_stratified_subset", capture_subset)
    validation, test = prediction_sets()
    monkeypatch.setattr(
        experiment,
        "collect_predictions",
        lambda dataset, *args, **kwargs: validation if dataset.name.startswith("sampled-val") else test,
    )
    monkeypatch.setattr(experiment, "run_experiment", lambda *args, **kwargs: {"ok": True})

    experiment.run_from_paths(
        index_root=index_root,
        source_data_root=source_root,
        checkpoint=checkpoint,
        output_root=tmp_path / "output",
        max_validation_samples_per_class=512,
        max_test_samples_per_class=1024,
        sampling_seed=20260823,
    )

    assert sampled == [
        ("val.csv", 512, 20260823),
        ("test.csv", 1024, 20260823),
    ]


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
    assert args.max_validation_samples_per_class == 512
    assert args.max_test_samples_per_class == 1024
    assert args.sampling_seed == 20260823


def test_training_wrapper_exposes_uncertainty_mode():
    script = (Path(__file__).parents[1] / "scripts" / "train_cvb_behavior.ps1").read_text(
        encoding="utf-8"
    )

    assert "'smoke','train','evaluate','uncertainty'" in script
    assert "cattle_health_app.behavior.uncertainty_experiment" in script
    assert "--minimum-actionable-coverage" in script


def test_class_stratified_subset_is_deterministic_and_capped_per_class():
    class Dataset(torch.utils.data.Dataset):
        def __init__(self, reverse=False):
            samples = [
                SimpleNamespace(sample_id=f"class-{label}-{index}", label_id=label)
                for label in (1, 2, 3)
                for index in range(5)
            ]
            self.samples = list(reversed(samples)) if reverse else samples

        def __len__(self):
            return len(self.samples)

        def __getitem__(self, index):
            return self.samples[index].sample_id

    first = experiment.class_stratified_subset(
        Dataset(), max_samples_per_class=2, seed=20260823
    )
    second = experiment.class_stratified_subset(
        Dataset(reverse=True), max_samples_per_class=2, seed=20260823
    )

    first_ids = {sample.sample_id for sample in first.samples}
    second_ids = {sample.sample_id for sample in second.samples}
    assert first_ids == second_ids
    assert len(first) == 6
    assert first.source_sample_count == 15
    assert first.sampling_method == "class_stratified_sample_id_sha256"
    assert first.sampling_seed == 20260823
    assert first.max_samples_per_class == 2
    assert {
        label: sum(sample.label_id == label for sample in first.samples)
        for label in (1, 2, 3)
    } == {1: 2, 2: 2, 3: 2}


@pytest.mark.parametrize("limit,seed", [(0, 1), (True, 1), (1, -1), (1, True)])
def test_class_stratified_subset_validates_sampling_settings(limit, seed):
    dataset = SimpleNamespace(samples=[SimpleNamespace(sample_id="x", label_id=1)])
    dataset.__len__ = lambda: 1

    with pytest.raises((TypeError, ValueError)):
        experiment.class_stratified_subset(dataset, limit, seed)

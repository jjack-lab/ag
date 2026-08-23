"""Leakage-safe offline behavior confidence calibration experiment."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from .cvb_labels import CVB_LABELS
from .dataset import CvbClipDataset
from .model import load_behavior_checkpoint
from .uncertainty import (
    calibration_metrics,
    fit_temperature,
    normalized_entropy,
    probabilities_from_logits,
    rejection_mask,
    select_rejection_policy,
    selective_metrics,
)


@dataclass(frozen=True)
class PredictionSet:
    sample_ids: tuple[str, ...]
    logits: np.ndarray
    labels: np.ndarray
    source_sample_count: int | None = None
    sampling_method: str = "all"
    sampling_seed: int | None = None
    max_samples_per_class: int | None = None


class ClassStratifiedSubset(torch.utils.data.Dataset):
    def __init__(self, dataset, indices, seed: int, max_samples_per_class: int):
        self.dataset = dataset
        self.indices = tuple(indices)
        self.samples = [dataset.samples[index] for index in self.indices]
        self.source_sample_count = len(dataset)
        self.sampling_method = "class_stratified_sample_id_sha256"
        self.sampling_seed = seed
        self.max_samples_per_class = max_samples_per_class

    def __len__(self):
        return len(self.indices)

    def __getitem__(self, index):
        return self.dataset[self.indices[index]]


def class_stratified_subset(dataset, max_samples_per_class: int, seed: int):
    """Select a reproducible per-class cap using only labels and sample IDs."""

    if (
        isinstance(max_samples_per_class, bool)
        or not isinstance(max_samples_per_class, int)
        or max_samples_per_class <= 0
    ):
        raise ValueError("max_samples_per_class must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    samples = getattr(dataset, "samples", None)
    if samples is None or len(samples) != len(dataset) or not samples:
        raise ValueError("dataset must expose one ordered sample record per item")
    grouped = {}
    seen_ids = set()
    for index, sample in enumerate(samples):
        sample_id = getattr(sample, "sample_id", None)
        label_id = getattr(sample, "label_id", None)
        if not isinstance(sample_id, str) or not sample_id or sample_id in seen_ids:
            raise ValueError("dataset sample IDs must be non-empty and unique")
        if isinstance(label_id, bool) or not isinstance(label_id, (int, np.integer)):
            raise ValueError("dataset samples must expose integer label IDs")
        seen_ids.add(sample_id)
        rank = hashlib.sha256(f"{seed}:{sample_id}".encode("utf-8")).digest()
        grouped.setdefault(int(label_id), []).append((rank, sample_id, index))
    selected = []
    for candidates in grouped.values():
        candidates.sort(key=lambda item: (item[0], item[1]))
        selected.extend(candidates[:max_samples_per_class])
    selected.sort(key=lambda item: item[1])
    return ClassStratifiedSubset(
        dataset,
        [item[2] for item in selected],
        seed=seed,
        max_samples_per_class=max_samples_per_class,
    )


def collect_predictions(
    dataset, model, device="cpu", batch_size: int = 8, workers: int = 0
) -> PredictionSet:
    """Collect raw logits in deterministic manifest order without augmentation."""

    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")
    if isinstance(workers, bool) or not isinstance(workers, int) or workers < 0:
        raise ValueError("workers must be a nonnegative integer")
    if not isinstance(model, torch.nn.Module):
        raise TypeError("model must be a torch module")
    samples = getattr(dataset, "samples", None)
    if samples is None or len(samples) != len(dataset) or not samples:
        raise ValueError("dataset must expose one ordered sample record per item")
    sample_ids = tuple(getattr(sample, "sample_id", None) for sample in samples)
    if any(not isinstance(item, str) or not item for item in sample_ids):
        raise ValueError("dataset samples must expose non-empty sample IDs")
    target_device = torch.device(device)
    model.to(target_device).eval()
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=workers,
    )
    logits_rows = []
    label_rows = []
    with torch.inference_mode():
        for clips, labels in loader:
            output = model(clips.to(target_device, non_blocking=target_device.type == "cuda"))
            if not isinstance(output, torch.Tensor) or output.ndim != 2:
                raise ValueError("behavior model must return a two-dimensional logits tensor")
            if len(output) != len(labels) or output.shape[1] < 2:
                raise ValueError("behavior logits must align with labels and contain two classes")
            if not torch.isfinite(output).all():
                raise ValueError("behavior logits must be finite")
            logits_rows.append(output.detach().cpu().to(torch.float64).numpy())
            label_rows.append(labels.detach().cpu().to(torch.int64).numpy())
    logits = np.concatenate(logits_rows, axis=0)
    labels = np.concatenate(label_rows, axis=0)
    return _validated_prediction_set(
        PredictionSet(
            sample_ids=sample_ids,
            logits=logits,
            labels=labels,
            source_sample_count=getattr(dataset, "source_sample_count", len(dataset)),
            sampling_method=getattr(dataset, "sampling_method", "all"),
            sampling_seed=getattr(dataset, "sampling_seed", None),
            max_samples_per_class=getattr(dataset, "max_samples_per_class", None),
        ),
        "collected",
    )


def _validated_prediction_set(values: PredictionSet, name: str) -> PredictionSet:
    if not isinstance(values, PredictionSet):
        raise TypeError(f"{name} must be a PredictionSet")
    sample_ids = tuple(values.sample_ids)
    if not sample_ids or any(not isinstance(item, str) or not item for item in sample_ids):
        raise ValueError(f"{name} sample IDs must be non-empty strings")
    if len(set(sample_ids)) != len(sample_ids):
        raise ValueError(f"{name} sample IDs must be unique")
    logits = np.asarray(values.logits, dtype=np.float64)
    labels = np.asarray(values.labels)
    probabilities = probabilities_from_logits(logits)
    if len(sample_ids) != len(probabilities) or labels.ndim != 1 or len(labels) != len(sample_ids):
        raise ValueError(f"{name} predictions, labels, and sample IDs must align")
    if not np.issubdtype(labels.dtype, np.integer):
        raise ValueError(f"{name} labels must use an integer dtype")
    labels = labels.astype(np.int64, copy=False)
    if (labels < 0).any() or (labels >= logits.shape[1]).any():
        raise ValueError(f"{name} labels must be in the class index range")
    source_count = (
        len(sample_ids)
        if values.source_sample_count is None
        else values.source_sample_count
    )
    if (
        isinstance(source_count, bool)
        or not isinstance(source_count, int)
        or source_count < len(sample_ids)
    ):
        raise ValueError(f"{name} source sample count must cover selected samples")
    if not isinstance(values.sampling_method, str) or not values.sampling_method:
        raise ValueError(f"{name} sampling method must be a non-empty string")
    return PredictionSet(
        sample_ids,
        logits,
        labels,
        source_sample_count=source_count,
        sampling_method=values.sampling_method,
        sampling_seed=values.sampling_seed,
        max_samples_per_class=values.max_samples_per_class,
    )


def _validated_sha256(value: str, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _selection_metadata(values: PredictionSet) -> dict:
    digest = hashlib.sha256()
    for sample_id in values.sample_ids:
        digest.update(sample_id.encode("utf-8"))
        digest.update(b"\n")
    return {
        "sampling_method": values.sampling_method,
        "sampling_seed": values.sampling_seed,
        "max_samples_per_class": values.max_samples_per_class,
        "source_sample_count": values.source_sample_count,
        "selected_sample_count": len(values.sample_ids),
        "sample_ids_sha256": digest.hexdigest(),
    }


def save_prediction_cache(path, values: PredictionSet, fingerprint: dict) -> None:
    """Atomically cache raw logits with an exact input fingerprint."""

    values = _validated_prediction_set(values, "cache")
    if not isinstance(fingerprint, dict):
        raise TypeError("cache fingerprint must be a dictionary")
    fingerprint_json = json.dumps(fingerprint, sort_keys=True, allow_nan=False)
    metadata = {
        "fingerprint": json.loads(fingerprint_json),
        "source_sample_count": values.source_sample_count,
        "sampling_method": values.sampling_method,
        "sampling_seed": values.sampling_seed,
        "max_samples_per_class": values.max_samples_per_class,
    }
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        dir=str(destination.parent),
        prefix=f".{destination.name}.",
        suffix=".tmp",
        delete=False,
    )
    temporary = Path(handle.name)
    handle.close()
    try:
        with temporary.open("wb") as target:
            np.savez_compressed(
                target,
                sample_ids=np.asarray(values.sample_ids, dtype=np.str_),
                logits=values.logits,
                labels=values.labels,
                metadata=np.asarray(
                    json.dumps(metadata, sort_keys=True, allow_nan=False),
                    dtype=np.str_,
                ),
            )
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def load_prediction_cache(path, fingerprint: dict) -> PredictionSet | None:
    """Load a cache only when its fingerprint exactly matches current inputs."""

    source = Path(path)
    if not source.is_file():
        return None
    try:
        expected = json.loads(json.dumps(fingerprint, sort_keys=True, allow_nan=False))
        with np.load(source, allow_pickle=False) as payload:
            metadata = json.loads(str(payload["metadata"].item()))
            if metadata.get("fingerprint") != expected:
                return None
            values = PredictionSet(
                sample_ids=tuple(str(item) for item in payload["sample_ids"].tolist()),
                logits=np.asarray(payload["logits"], dtype=np.float64),
                labels=np.asarray(payload["labels"], dtype=np.int64),
                source_sample_count=metadata.get("source_sample_count"),
                sampling_method=metadata.get("sampling_method", "all"),
                sampling_seed=metadata.get("sampling_seed"),
                max_samples_per_class=metadata.get("max_samples_per_class"),
            )
        return _validated_prediction_set(values, "cached")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def _json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(
            payload, ensure_ascii=False, indent=2, allow_nan=False
        )
        + "\n",
        encoding="utf-8",
    )


def _protocol(probabilities, labels, accepted, uncertain_label_ids) -> dict:
    return {
        "calibration": calibration_metrics(probabilities, labels),
        "selective": selective_metrics(
            probabilities,
            labels,
            accepted,
            uncertain_label_ids=uncertain_label_ids,
        ),
    }


def _write_comparison(path: Path, protocols: dict) -> None:
    fields = (
        "protocol",
        "accuracy",
        "macro_f1",
        "negative_log_likelihood",
        "expected_calibration_error",
        "multiclass_brier_score",
        "coverage",
        "actionable_coverage",
        "selective_accuracy",
        "selective_macro_f1",
        "selective_risk",
        "unsafe_detection_auroc",
        "unsafe_detection_auprc",
    )
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        for name, payload in protocols.items():
            calibration = payload["calibration"]
            selective = payload["selective"]
            writer.writerow(
                {
                    "protocol": name,
                    **{field: calibration.get(field) for field in fields if field in calibration},
                    **{field: selective.get(field) for field in fields if field in selective},
                }
            )


def _write_predictions(
    path: Path,
    values: PredictionSet,
    uncalibrated: np.ndarray,
    calibrated: np.ndarray,
    accepted_fixed: np.ndarray,
    accepted_joint: np.ndarray,
) -> None:
    fields = (
        "sample_id",
        "label_id",
        "uncalibrated_prediction_id",
        "uncalibrated_confidence",
        "calibrated_prediction_id",
        "calibrated_confidence",
        "calibrated_normalized_entropy",
        "temperature_fixed_045_accepted",
        "temperature_joint_rejection_accepted",
    )
    entropy = normalized_entropy(calibrated)
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        for index, sample_id in enumerate(values.sample_ids):
            writer.writerow(
                {
                    "sample_id": sample_id,
                    "label_id": int(values.labels[index]),
                    "uncalibrated_prediction_id": int(uncalibrated[index].argmax()),
                    "uncalibrated_confidence": float(uncalibrated[index].max()),
                    "calibrated_prediction_id": int(calibrated[index].argmax()),
                    "calibrated_confidence": float(calibrated[index].max()),
                    "calibrated_normalized_entropy": float(entropy[index]),
                    "temperature_fixed_045_accepted": bool(accepted_fixed[index]),
                    "temperature_joint_rejection_accepted": bool(accepted_joint[index]),
                }
            )


def _publish_directory(staging: Path, output: Path) -> None:
    backup = None
    try:
        if output.exists():
            backup = Path(
                tempfile.mkdtemp(prefix=f".{output.name}.backup-", dir=str(output.parent))
            )
            backup.rmdir()
            os.replace(output, backup)
        os.replace(staging, output)
    except Exception:
        if backup is not None and backup.exists() and not output.exists():
            os.replace(backup, output)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)
        if backup is not None and backup.exists():
            shutil.rmtree(backup)


def run_experiment(
    validation: PredictionSet,
    test: PredictionSet,
    output_root,
    *,
    checkpoint_sha256: str,
    validation_manifest_sha256: str,
    test_manifest_sha256: str,
    model_version: str,
    confidence_grid=None,
    entropy_grid=None,
    minimum_actionable_coverage: float = 0.60,
    uncertain_label_ids=(0, 9, 10),
) -> dict:
    """Fit on validation predictions and evaluate frozen protocols on test data."""

    validation = _validated_prediction_set(validation, "validation")
    test = _validated_prediction_set(test, "test")
    if validation.logits.shape[1] != test.logits.shape[1]:
        raise ValueError("validation and test class counts must match")
    checkpoint_hash = _validated_sha256(checkpoint_sha256, "checkpoint_sha256")
    validation_hash = _validated_sha256(
        validation_manifest_sha256, "validation_manifest_sha256"
    )
    test_hash = _validated_sha256(test_manifest_sha256, "test_manifest_sha256")
    if not isinstance(model_version, str) or not model_version.strip():
        raise ValueError("model_version must be a non-empty string")
    confidence_grid = (
        confidence_grid
        if confidence_grid is not None
        else [value / 100.0 for value in range(25, 91, 5)]
    )
    entropy_grid = (
        entropy_grid
        if entropy_grid is not None
        else [value / 100.0 for value in range(50, 101, 5)]
    )

    temperature = fit_temperature(validation.logits, validation.labels)
    validation_calibrated = probabilities_from_logits(
        validation.logits, temperature
    )
    policy = select_rejection_policy(
        validation_calibrated,
        validation.labels,
        confidence_grid,
        entropy_grid,
        minimum_actionable_coverage=minimum_actionable_coverage,
        uncertain_label_ids=uncertain_label_ids,
    )

    uncalibrated = probabilities_from_logits(test.logits)
    calibrated = probabilities_from_logits(test.logits, temperature)
    uncalibrated_fixed = ~rejection_mask(uncalibrated, 0.45, 1.0)
    calibrated_fixed = ~rejection_mask(calibrated, 0.45, 1.0)
    calibrated_joint = ~rejection_mask(
        calibrated, policy.min_confidence, policy.max_normalized_entropy
    )
    protocols = {
        "uncalibrated_fixed_045": _protocol(
            uncalibrated, test.labels, uncalibrated_fixed, uncertain_label_ids
        ),
        "temperature_fixed_045": _protocol(
            calibrated, test.labels, calibrated_fixed, uncertain_label_ids
        ),
        "temperature_joint_rejection": _protocol(
            calibrated, test.labels, calibrated_joint, uncertain_label_ids
        ),
    }
    uncalibrated_quality = protocols["uncalibrated_fixed_045"]["calibration"]
    calibrated_quality = protocols["temperature_fixed_045"]["calibration"]
    calibration_improved = (
        calibrated_quality["negative_log_likelihood"]
        < uncalibrated_quality["negative_log_likelihood"]
        or calibrated_quality["expected_calibration_error"]
        < uncalibrated_quality["expected_calibration_error"]
    )
    result = {
        "schema_version": 1,
        "model_version": model_version,
        "checkpoint_sha256": checkpoint_hash,
        "validation_manifest_sha256": validation_hash,
        "test_manifest_sha256": test_hash,
        "validation_sample_count": len(validation.sample_ids),
        "test_sample_count": len(test.sample_ids),
        "validation_selection": _selection_metadata(validation),
        "test_selection": _selection_metadata(test),
        "selection_split": "validation",
        "temperature": temperature,
        "policy": policy.to_dict(),
        "protocols": protocols,
        "runtime_integration_gate": {
            "calibration_improved_on_test": calibration_improved,
            "validation_coverage_satisfied": (
                policy.validation_actionable_coverage
                >= policy.minimum_actionable_coverage
            ),
            "integration_recommended": (
                calibration_improved
                and policy.validation_actionable_coverage
                >= policy.minimum_actionable_coverage
            ),
        },
    }
    calibration_artifact = {
        "schema_version": 1,
        "model_version": model_version,
        "checkpoint_sha256": checkpoint_hash,
        "validation_manifest_sha256": validation_hash,
        "validation_selection": _selection_metadata(validation),
        "selection_split": "validation",
        "temperature": temperature,
        "policy": policy.to_dict(),
    }

    output = Path(output_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=str(output.parent))
    )
    try:
        _json(staging / "calibration.json", calibration_artifact)
        _json(staging / "experiment_metrics.json", result)
        _write_comparison(staging / "protocol_comparison.csv", protocols)
        _write_predictions(
            staging / "test_predictions.csv",
            test,
            uncalibrated,
            calibrated,
            calibrated_fixed,
            calibrated_joint,
        )
        _publish_directory(staging, output)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return result


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _dataset_sample_ids_sha256(dataset) -> str:
    digest = hashlib.sha256()
    samples = getattr(dataset, "samples", None)
    if samples is None or len(samples) != len(dataset):
        raise ValueError("dataset must expose ordered samples for cache fingerprinting")
    for sample in samples:
        sample_id = getattr(sample, "sample_id", None)
        if not isinstance(sample_id, str) or not sample_id:
            raise ValueError("dataset samples must expose non-empty sample IDs")
        digest.update(sample_id.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def run_from_paths(
    *,
    index_root,
    source_data_root,
    checkpoint,
    output_root,
    device="cpu",
    batch_size: int = 8,
    workers: int = 0,
    confidence_grid=None,
    entropy_grid=None,
    minimum_actionable_coverage: float = 0.60,
    max_validation_samples_per_class: int | None = None,
    max_test_samples_per_class: int | None = None,
    sampling_seed: int = 20260823,
    prediction_cache_root=None,
) -> dict:
    """Load fixed validation/test splits, collect logits, and run the experiment."""

    index_path = Path(index_root)
    source_path = Path(source_data_root)
    checkpoint_path = Path(checkpoint)
    validation_manifest = index_path / "val.csv"
    test_manifest = index_path / "test.csv"
    for path, label in (
        (validation_manifest, "validation manifest"),
        (test_manifest, "test manifest"),
        (checkpoint_path, "checkpoint"),
    ):
        if not path.is_file():
            raise ValueError(f"{label} does not exist: {path}")
    if not source_path.is_dir():
        raise ValueError(f"source data root does not exist: {source_path}")

    loaded = load_behavior_checkpoint(checkpoint_path, device=device)
    size = loaded.metadata.input_size
    validation_dataset = CvbClipDataset(
        validation_manifest, source_path, training=False, size=size
    )
    test_dataset = CvbClipDataset(
        test_manifest, source_path, training=False, size=size
    )
    if max_validation_samples_per_class is not None:
        validation_dataset = class_stratified_subset(
            validation_dataset, max_validation_samples_per_class, sampling_seed
        )
    if max_test_samples_per_class is not None:
        test_dataset = class_stratified_subset(
            test_dataset, max_test_samples_per_class, sampling_seed
        )
    checkpoint_hash = _sha256_file(checkpoint_path)
    validation_hash = _sha256_file(validation_manifest)
    test_hash = _sha256_file(test_manifest)
    cache_root = (
        Path(prediction_cache_root)
        if prediction_cache_root is not None
        else Path(str(output_root) + ".prediction_cache")
    )

    def predictions_for(split, dataset, manifest_hash):
        fingerprint = {
            "checkpoint_sha256": checkpoint_hash,
            "manifest_sha256": manifest_hash,
            "sample_ids_sha256": _dataset_sample_ids_sha256(dataset),
            "model_version": loaded.metadata.model_version,
        }
        cache_path = cache_root / f"{split}.npz"
        cached = load_prediction_cache(cache_path, fingerprint)
        if cached is not None:
            return cached
        collected = collect_predictions(
            dataset,
            loaded.model,
            device=device,
            batch_size=batch_size,
            workers=workers,
        )
        save_prediction_cache(cache_path, collected, fingerprint)
        return collected

    validation_predictions = predictions_for(
        "validation", validation_dataset, validation_hash
    )
    test_predictions = predictions_for("test", test_dataset, test_hash)
    uncertain_ids = tuple(
        label_id - 1 for label_id, label in CVB_LABELS.items() if label.uncertain
    )
    return run_experiment(
        validation_predictions,
        test_predictions,
        output_root,
        checkpoint_sha256=checkpoint_hash,
        validation_manifest_sha256=validation_hash,
        test_manifest_sha256=test_hash,
        model_version=loaded.metadata.model_version,
        confidence_grid=confidence_grid,
        entropy_grid=entropy_grid,
        minimum_actionable_coverage=minimum_actionable_coverage,
        uncertain_label_ids=uncertain_ids,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calibrate and evaluate selective CVB behavior prediction"
    )
    parser.add_argument("--index-root", required=True)
    parser.add_argument("--source-data-root", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument(
        "--device", default="cuda" if torch.cuda.is_available() else "cpu"
    )
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--minimum-actionable-coverage", type=float, default=0.60)
    parser.add_argument("--confidence-grid", type=float, nargs="+")
    parser.add_argument("--entropy-grid", type=float, nargs="+")
    parser.add_argument("--max-validation-samples-per-class", type=int, default=512)
    parser.add_argument("--max-test-samples-per-class", type=int, default=1024)
    parser.add_argument("--sampling-seed", type=int, default=20260823)
    parser.add_argument("--prediction-cache-root")
    return parser


def main(argv=None) -> dict:
    args = build_parser().parse_args(argv)
    result = run_from_paths(
        index_root=args.index_root,
        source_data_root=args.source_data_root,
        checkpoint=args.checkpoint,
        output_root=args.output_root,
        device=args.device,
        batch_size=args.batch_size,
        workers=args.workers,
        confidence_grid=args.confidence_grid,
        entropy_grid=args.entropy_grid,
        minimum_actionable_coverage=args.minimum_actionable_coverage,
        max_validation_samples_per_class=args.max_validation_samples_per_class,
        max_test_samples_per_class=args.max_test_samples_per_class,
        sampling_seed=args.sampling_seed,
        prediction_cache_root=args.prediction_cache_root,
    )
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return result


if __name__ == "__main__":
    main()

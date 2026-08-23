import csv
import hashlib
import json

import numpy as np
import pytest

from cattle_health_app.behavior.cross_domain_experiment import (
    ExternalPrediction,
    ProtocolViolation,
)
from cattle_health_app.behavior.external_download import DownloadBlocked
from cattle_health_app.behavior.external_video_dataset import ExternalVideoSample
from scripts.prepare_external_behavior_data import main as prepare_main
import scripts.run_cross_domain_behavior_experiment as experiment_cli
from scripts.run_cross_domain_behavior_experiment import main as experiment_main


def _registry(path, root, license_status="verified"):
    payload = {
        "schema_version": 1,
        "datasets": [
            {
                "dataset_id": "cbvd5",
                "name": "CBVD-5",
                "version": "kaggle-version-11",
                "official_url": "https://example.test/paper",
                "access_url": "https://example.test/dataset",
                "license_name": "CC0",
                "license_url": "https://example.test/license",
                "license_status": license_status,
                "intended_use": "external_test_only",
                "storage_root": "data/external/cbvd5",
                "max_download_bytes": 1024,
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _inventory(path):
    payload = {
        "dataset_id": "cbvd5",
        "dataset_version": 11,
        "dataset_total_bytes": 2000,
        "files": [
            {
                "path": "videos/videos/618.mp4",
                "url": "https://example.test/618.mp4",
                "bytes": 3,
                "sha256": hashlib.sha256(b"abc").hexdigest(),
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_inspect_reports_budget_without_downloading(tmp_path, monkeypatch, capsys):
    registry = _registry(tmp_path / "registry.json", tmp_path)
    inventory = _inventory(tmp_path / "inventory.json")

    def forbidden(*args, **kwargs):
        raise AssertionError("inspect must not download")

    monkeypatch.setattr(
        "scripts.prepare_external_behavior_data.acquire_file", forbidden
    )
    result = prepare_main(
        [
            "--project-root",
            str(tmp_path),
            "--registry",
            str(registry),
            "--inventory",
            str(inventory),
            "inspect",
            "--dataset",
            "cbvd5",
        ]
    )

    report = json.loads(capsys.readouterr().out)
    assert result == 0
    assert report["license_status"] == "verified"
    assert report["download_budget_bytes"] == 1024
    assert report["declared_dataset_bytes"] == 2000
    assert report["operation"] == "inspect_only"


def test_acquire_refuses_an_unverified_license(tmp_path):
    registry = _registry(
        tmp_path / "registry.json", tmp_path, license_status="verify_before_download"
    )
    inventory = _inventory(tmp_path / "inventory.json")

    with pytest.raises(DownloadBlocked, match="not verified"):
        prepare_main(
            [
                "--project-root",
                str(tmp_path),
                "--registry",
                str(registry),
                "--inventory",
                str(inventory),
                "acquire",
                "--dataset",
                "cbvd5",
                "--file",
                "videos/videos/618.mp4",
            ]
        )


def test_prepare_writes_test_only_manifest_and_exclusions(tmp_path):
    registry = _registry(tmp_path / "registry.json", tmp_path)
    inventory = _inventory(tmp_path / "inventory.json")
    storage = tmp_path / "data" / "external" / "cbvd5"
    video = storage / "raw" / "videos" / "videos" / "618.mp4"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"video-evidence")
    second_video = video.with_name("619.mp4")
    second_video.write_bytes(b"second-video-evidence")
    annotation = storage / "archives" / "ava_train_v2.1.csv"
    annotation.parent.mkdir(parents=True)
    annotation.write_text(
        "618,2,0.1,0.2,0.4,0.7,1,7\n"
        "618,2,0.1,0.2,0.4,0.7,3,7\n"
        "619,2,0.1,0.2,0.4,0.7,1,8\n"
        "619,2,0.1,0.2,0.4,0.7,3,8\n"
        "bad,row\n",
        encoding="utf-8",
    )

    result = prepare_main(
        [
            "--project-root",
            str(tmp_path),
            "--registry",
            str(registry),
            "--inventory",
            str(inventory),
            "prepare",
            "--dataset",
            "cbvd5",
            "--tier",
            "strict",
            "--annotation",
            str(annotation),
            "--max-per-class",
            "1",
        ]
    )

    manifest_root = storage / "manifests"
    with (manifest_root / "evaluation_clips_strict.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        row = next(csv.DictReader(handle))
    assert result == 0
    assert row["mapped_label"] == "grazing"
    assert row["split"] == "test"
    assert row["source_video_path"].endswith(("618.mp4", "619.mp4"))
    with (manifest_root / "source_videos.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        assert len(list(csv.DictReader(handle))) == 1
    assert (manifest_root / "excluded_samples.csv").is_file()
    summary = json.loads((manifest_root / "manifest_summary.json").read_text("utf-8"))
    assert summary["strict"]["included_samples"] == 1
    assert summary["strict"]["parser_exclusions"] == 1


def test_experiment_dry_run_writes_hash_bound_protocol(tmp_path):
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"checkpoint")
    checkpoint_hash = hashlib.sha256(b"checkpoint").hexdigest()
    calibration = tmp_path / "calibration.json"
    calibration.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "checkpoint_sha256": checkpoint_hash,
                "validation_manifest_sha256": "b" * 64,
                "selection_split": "validation",
                "temperature": 2.0,
                "policy": {
                    "selection_split": "validation",
                    "min_confidence": 0.45,
                    "max_normalized_entropy": 0.85,
                },
            }
        ),
        encoding="utf-8",
    )
    strict_manifest = tmp_path / "strict.csv"
    strict_manifest.write_text(
        "sample_id,split,mapping_tier,mapped_label\na,test,strict,grazing\n",
        encoding="utf-8",
    )
    extended_manifest = tmp_path / "extended.csv"
    extended_manifest.write_text(
        "sample_id,split,mapping_tier,mapped_label\na,test,extended,grazing\n",
        encoding="utf-8",
    )
    output = tmp_path / "result"

    result = experiment_main(
        [
            "--manifest",
            str(strict_manifest),
            "--manifest",
            str(extended_manifest),
            "--output",
            str(output),
            "--checkpoint",
            str(checkpoint),
            "--calibration",
            str(calibration),
            "--seed",
            "20260823",
            "--dry-run",
        ]
    )

    protocol = json.loads((output / "protocol.json").read_text("utf-8"))
    assert result == 0
    assert "status" not in protocol
    assert json.loads((output / "preflight.json").read_text("utf-8"))[
        "status"
    ] == "validated_not_run"
    assert protocol["checkpoint_sha256"] == checkpoint_hash
    assert protocol["external_sample_count"] == 2
    assert protocol["external_sample_counts"] == {"extended": 1, "strict": 1}
    assert protocol["external_class_counts"] == {
        "extended": {"grazing": 1},
        "strict": {"grazing": 1},
    }
    assert protocol["manifest_sha256s"] == {
        "extended": hashlib.sha256(extended_manifest.read_bytes()).hexdigest(),
        "strict": hashlib.sha256(strict_manifest.read_bytes()).hexdigest(),
    }
    assert protocol["seed"] == 20260823


def test_experiment_protocol_preserves_preexisting_manual_audit_directory(tmp_path):
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"checkpoint")
    checkpoint_hash = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    calibration = tmp_path / "calibration.json"
    calibration.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "checkpoint_sha256": checkpoint_hash,
                "validation_manifest_sha256": "b" * 64,
                "selection_split": "validation",
                "temperature": 2.0,
                "policy": {
                    "selection_split": "validation",
                    "min_confidence": 0.45,
                    "max_normalized_entropy": 0.85,
                },
            }
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "strict.csv"
    manifest.write_text(
        "sample_id,split,mapping_tier,mapped_label\na,test,strict,grazing\n",
        encoding="utf-8",
    )
    output = tmp_path / "result"
    audit = output / "audit"
    audit.mkdir(parents=True)
    (audit / "manual.jpg").write_bytes(b"review evidence")

    assert (
        experiment_main(
            [
                "--manifest",
                str(manifest),
                "--output",
                str(output),
                "--checkpoint",
                str(checkpoint),
                "--calibration",
                str(calibration),
                "--dry-run",
            ]
        )
        == 0
    )
    assert (audit / "manual.jpg").read_bytes() == b"review evidence"
    assert (output / "protocol.json").is_file()


def test_experiment_executes_frozen_baseline_and_writes_auditable_results(
    monkeypatch, tmp_path
):
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"checkpoint")
    checkpoint_hash = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    calibration = tmp_path / "calibration.json"
    calibration.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "checkpoint_sha256": checkpoint_hash,
                "validation_manifest_sha256": "b" * 64,
                "selection_split": "validation",
                "temperature": 2.0,
                "policy": {
                    "selection_split": "validation",
                    "min_confidence": 0.45,
                    "max_normalized_entropy": 0.85,
                },
            }
        ),
        encoding="utf-8",
    )
    manifests = []
    for tier in ("strict", "extended"):
        manifest = tmp_path / (tier + ".csv")
        manifest.write_text(
            "sample_id,split,mapping_tier,mapped_label\nshared,test,{},grazing\n".format(tier),
            encoding="utf-8",
        )
        manifests.append(manifest)

    def sample(tier):
        return ExternalVideoSample(
            sample_id="shared",
            source_group_id="group-1",
            source_video_id="1",
            source_video_path="data/external/cbvd5/raw/videos/videos/1.mp4",
            start_second=0.0,
            end_second=4.0,
            crop_box=(0.1, 0.1, 0.9, 0.9),
            mapped_label="grazing",
            mapping_tier=tier,
            source_labels=("foraging",),
            source_sha256="a" * 64,
        )

    monkeypatch.setattr(
        experiment_cli,
        "load_external_samples",
        lambda path, root: (sample("strict" if "strict" in str(path) else "extended"),),
        raising=False,
    )
    monkeypatch.setattr(
        experiment_cli, "FrozenX3DLogitPredictor", lambda *args, **kwargs: object(), raising=False
    )
    calls = []

    def collect(samples, root, **kwargs):
        calls.append(tuple(samples))
        frame_transform = kwargs.get("frame_transform")
        if frame_transform is not None:
            frames = tuple(np.full((8, 8, 3), 100, np.uint8) for _ in range(4))
            seen = set()
            for row in samples:
                if row.sample_id not in seen:
                    frame_transform(frames, row)
                    seen.add(row.sample_id)
        features = {
            "mean_brightness": 0.5,
            "mean_dark_ratio": 0.1,
            "mean_overexposed_ratio": 0.1,
            "mean_laplacian_variance": 0.2,
            "track_continuity": 1.0,
            "track_truncation_ratio": 0.0,
        }
        logits = np.zeros(12, dtype=np.float64)
        logits[1] = 5.0
        return tuple(
            ExternalPrediction(
                sample_id=row.sample_id,
                mapping_tier=row.mapping_tier,
                true_label=1,
                logits=tuple(logits),
                quality_features=features,
            )
            for row in samples
        )

    monkeypatch.setattr(
        experiment_cli,
        "collect_external_predictions_reusing_physical_clips",
        collect,
        raising=False,
    )
    output = tmp_path / "result"

    base_args = [
            "--manifest",
            str(manifests[0]),
            "--manifest",
            str(manifests[1]),
            "--output",
            str(output),
            "--checkpoint",
            str(checkpoint),
            "--calibration",
            str(calibration),
            "--project-root",
            str(tmp_path),
            "--stress-levels",
            "0,1",
            "--stress-per-class",
            "1",
        ]
    assert experiment_main(base_args + ["--dry-run"]) == 0
    assert json.loads((output / "preflight.json").read_text("utf-8"))[
        "status"
    ] == "validated_not_run"
    result = experiment_main(base_args + ["--resume"])

    assert result == 0
    assert len(calls) == 7
    assert len(calls[0]) == 2
    assert json.loads((output / "quality_gate.json").read_text("utf-8"))[
        "policy_kind"
    ] == "predeclared_heuristic"
    assert (output / "baseline_raw_predictions.json").is_file()
    assert json.loads((output / "run_state.json").read_text("utf-8"))[
        "status"
    ] == "complete"
    assert json.loads((output / "metrics.json").read_text("utf-8"))[
        "sample_counts"
    ] == {"extended": 1, "strict": 1}
    assert json.loads((output / "metrics.json").read_text("utf-8"))[
        "inference_timing"
    ]["baseline"]["logical_sample_count"] == 2
    assert experiment_main(base_args + ["--resume"]) == 0
    assert len(calls) == 7
    assert json.loads((output / "run_state.json").read_text("utf-8"))[
        "stress_result_rows"
    ] == 48


def test_resume_alignment_rejects_an_incomplete_prediction_cache():
    sample = ExternalVideoSample(
        sample_id="expected",
        source_group_id="group-1",
        source_video_id="1",
        source_video_path="data/external/cbvd5/raw/videos/videos/1.mp4",
        start_second=0.0,
        end_second=4.0,
        crop_box=(0.1, 0.1, 0.9, 0.9),
        mapped_label="grazing",
        mapping_tier="strict",
        source_labels=("foraging",),
        source_sha256="a" * 64,
    )

    with pytest.raises(ProtocolViolation, match="aligned"):
        experiment_cli._validate_prediction_alignment((), (sample,))


def test_stress_cache_cannot_be_reused_as_a_different_condition(tmp_path):
    prediction = ExternalPrediction(
        sample_id="a",
        mapping_tier="strict",
        true_label=1,
        logits=tuple(np.zeros(12)),
        quality_features={"mean_brightness": 0.5},
    )
    cache = tmp_path / "stress.json"
    experiment_cli._write_prediction_cache(
        cache,
        "f" * 64,
        (prediction,),
        transformations=(
            {"sample_id": "a", "name": "blur", "level": 1},
        ),
        cache_identity={"kind": "stress", "degradation": "blur", "level": 1},
        sample_set_sha256="s" * 64,
    )

    with pytest.raises(ProtocolViolation, match="condition"):
        experiment_cli._load_prediction_cache(
            cache,
            "f" * 64,
            expected_cache_identity={
                "kind": "stress",
                "degradation": "occlusion",
                "level": 3,
            },
            expected_sample_set_sha256="s" * 64,
        )

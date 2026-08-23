import csv
import hashlib
import json

import pytest

from cattle_health_app.behavior.external_download import DownloadBlocked
from scripts.prepare_external_behavior_data import main as prepare_main
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
    manifest = tmp_path / "external.csv"
    manifest.write_text("sample_id,split\na,test\n", encoding="utf-8")
    output = tmp_path / "result"

    result = experiment_main(
        [
            "--manifest",
            str(manifest),
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
    assert protocol["status"] == "validated_not_run"
    assert protocol["checkpoint_sha256"] == checkpoint_hash
    assert protocol["manifest_sha256"] == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert protocol["seed"] == 20260823

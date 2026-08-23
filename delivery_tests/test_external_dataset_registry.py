import json
from pathlib import Path

import pytest

from cattle_health_app.behavior.external_registry import RegistryError, load_registry


def _record(**overrides):
    record = {
        "dataset_id": "cbvd5",
        "name": "CBVD-5",
        "version": "kaggle-current",
        "official_url": "https://www.nature.com/articles/s41598-024-65953-x",
        "access_url": "https://www.kaggle.com/datasets/fandaoerji/cbvd-5cow-behavior-video-dataset",
        "license_name": "unverified",
        "license_url": "",
        "license_status": "verify_before_download",
        "intended_use": "external_test_only",
        "storage_root": "data/external/cbvd5",
        "max_download_bytes": 5 * 1024**3,
    }
    record.update(overrides)
    return record


def _registry_file(tmp_path: Path, records):
    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps({"schema_version": 1, "datasets": records}), encoding="utf-8"
    )
    return path


def test_registry_loads_cbvd5_with_project_relative_storage(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()

    registry = load_registry(
        _registry_file(tmp_path, [_record()]), project_root=project_root
    )

    cbvd5 = registry.require("cbvd5")
    assert cbvd5.license_status == "verify_before_download"
    assert cbvd5.storage_root == project_root / "data" / "external" / "cbvd5"
    assert cbvd5.max_download_bytes == 5 * 1024**3


def test_registry_rejects_storage_outside_project(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()

    with pytest.raises(RegistryError, match="inside project_root"):
        load_registry(
            _registry_file(tmp_path, [_record(storage_root="../outside")]),
            project_root=project_root,
        )


def test_registry_rejects_unknown_license_status(tmp_path):
    with pytest.raises(RegistryError, match="license_status"):
        load_registry(
            _registry_file(tmp_path, [_record(license_status="probably-open")]),
            project_root=tmp_path,
        )


@pytest.mark.parametrize(
    "field",
    [
        "dataset_id",
        "name",
        "version",
        "official_url",
        "access_url",
        "license_name",
        "license_status",
        "intended_use",
        "storage_root",
        "max_download_bytes",
    ],
)
def test_registry_requires_exact_record_fields(tmp_path, field):
    record = _record()
    record.pop(field)

    with pytest.raises(RegistryError, match="fields"):
        load_registry(_registry_file(tmp_path, [record]), project_root=tmp_path)


def test_registry_rejects_duplicate_dataset_ids(tmp_path):
    with pytest.raises(RegistryError, match="duplicate dataset_id"):
        load_registry(
            _registry_file(tmp_path, [_record(), _record(name="Duplicate")]),
            project_root=tmp_path,
        )


def test_registry_require_reports_unknown_dataset(tmp_path):
    registry = load_registry(
        _registry_file(tmp_path, [_record()]), project_root=tmp_path
    )

    with pytest.raises(RegistryError, match="unknown dataset_id: missing"):
        registry.require("missing")

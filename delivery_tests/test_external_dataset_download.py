import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from cattle_health_app.behavior.external_download import (
    AcquisitionError,
    DownloadBlocked,
    RemoteFileSpec,
    UnsafeArchive,
    acquire_file,
    append_operation,
    safe_extract_zip,
)
from cattle_health_app.behavior.external_registry import DatasetRecord


def _record(tmp_path: Path, status="verified", budget=32):
    return DatasetRecord(
        dataset_id="sample",
        name="Sample",
        version="1",
        official_url="https://example.test/paper",
        access_url="https://example.test/data",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        license_status=status,
        intended_use="test",
        storage_root=tmp_path / "data" / "external" / "sample",
        max_download_bytes=budget,
    )


def _spec(content=b"hello", expected_size=None, sha256=None):
    return RemoteFileSpec(
        relative_path="archives/sample.bin",
        url="https://example.test/sample.bin",
        expected_size=len(content) if expected_size is None else expected_size,
        sha256=hashlib.sha256(content).hexdigest() if sha256 is None else sha256,
    )


def test_download_refuses_unverified_license_before_opening_stream(tmp_path):
    called = []

    with pytest.raises(DownloadBlocked, match="license"):
        acquire_file(
            _record(tmp_path, status="verify_before_download"),
            _spec(),
            opener=lambda url: called.append(url),
        )

    assert called == []


def test_download_refuses_declared_size_above_budget_before_stream(tmp_path):
    called = []

    with pytest.raises(DownloadBlocked, match="budget"):
        acquire_file(
            _record(tmp_path, budget=4),
            _spec(expected_size=5),
            opener=lambda url: called.append(url),
        )

    assert called == []


def test_download_removes_partial_file_when_stream_crosses_budget(tmp_path):
    record = _record(tmp_path, budget=5)
    spec = RemoteFileSpec(
        relative_path="archives/sample.bin",
        url="https://example.test/sample.bin",
        expected_size=None,
        sha256=hashlib.sha256(b"abcdef").hexdigest(),
    )

    with pytest.raises(DownloadBlocked, match="budget"):
        acquire_file(record, spec, opener=lambda url: [b"abc", b"def"])

    assert not (record.storage_root / spec.relative_path).exists()
    assert not (record.storage_root / (spec.relative_path + ".part")).exists()


def test_download_reuses_existing_file_after_hash_match(tmp_path):
    record = _record(tmp_path)
    spec = _spec()
    destination = record.storage_root / spec.relative_path
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"hello")

    result = acquire_file(
        record,
        spec,
        opener=lambda url: pytest.fail("existing valid file must not be downloaded"),
    )

    assert result.path == destination
    assert result.reused is True
    assert result.size == 5


def test_download_rejects_hash_mismatch_without_publishing_file(tmp_path):
    record = _record(tmp_path)
    spec = _spec(sha256="0" * 64)

    with pytest.raises(AcquisitionError, match="SHA-256"):
        acquire_file(record, spec, opener=lambda url: [b"hello"])

    assert not (record.storage_root / spec.relative_path).exists()


def test_safe_extract_rejects_zip_slip(tmp_path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(str(archive), "w") as handle:
        handle.writestr("../escape.mp4", b"bad")

    with pytest.raises(UnsafeArchive, match="outside extraction root"):
        safe_extract_zip(archive, tmp_path / "raw")

    assert not (tmp_path / "escape.mp4").exists()


def test_safe_extract_and_operation_log_are_auditable(tmp_path):
    archive = tmp_path / "ok.zip"
    with zipfile.ZipFile(str(archive), "w") as handle:
        handle.writestr("annotations/labels.csv", "label\nfeeding\n")
    output = tmp_path / "raw"

    extracted = safe_extract_zip(archive, output)
    log = tmp_path / "operations.jsonl"
    append_operation(log, {"operation": "extract", "count": len(extracted)})

    assert extracted == (output / "annotations" / "labels.csv",)
    assert extracted[0].read_text(encoding="utf-8") == "label\nfeeding\n"
    assert json.loads(log.read_text(encoding="utf-8"))["operation"] == "extract"

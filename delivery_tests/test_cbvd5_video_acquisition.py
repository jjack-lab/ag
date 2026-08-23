import hashlib

import pytest

from scripts.acquire_cbvd5_videos import (
    VideoAcquisitionError,
    acquire_inventory,
    validate_inventory,
)


def _rows():
    return [
        {"path": "videos/videos/1.mp4", "bytes": 3},
        {"path": "videos/videos/2.mp4", "bytes": 4},
    ]


def test_inventory_requires_expected_official_count_and_bytes():
    entries = validate_inventory(_rows(), expected_count=2, expected_bytes=7)

    assert [entry.relative_path for entry in entries] == [
        "videos/videos/1.mp4",
        "videos/videos/2.mp4",
    ]

    with pytest.raises(VideoAcquisitionError, match="total bytes"):
        validate_inventory(_rows(), expected_count=2, expected_bytes=8)


def test_acquisition_enforces_budget_and_records_hashes(tmp_path):
    entries = validate_inventory(_rows(), expected_count=2, expected_bytes=7)
    payloads = {"videos/videos/1.mp4": b"abc", "videos/videos/2.mp4": b"wxyz"}

    def downloader(entry, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payloads[entry.relative_path])

    results = acquire_inventory(
        entries,
        storage_root=tmp_path,
        max_download_bytes=7,
        downloader=downloader,
    )

    assert sum(result.size for result in results) == 7
    assert results[0].sha256 == hashlib.sha256(b"abc").hexdigest()
    assert all(not result.reused for result in results)


def test_acquisition_reuses_only_size_matching_files(tmp_path):
    entries = validate_inventory(_rows()[:1], expected_count=1, expected_bytes=3)
    existing = tmp_path / "raw" / "videos" / "videos" / "1.mp4"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"abc")

    def forbidden(*args):
        raise AssertionError("matching file must be reused")

    result = acquire_inventory(
        entries,
        storage_root=tmp_path,
        max_download_bytes=3,
        downloader=forbidden,
    )[0]

    assert result.reused is True


def test_inventory_rejects_escape_paths_and_budget_overflow(tmp_path):
    with pytest.raises(VideoAcquisitionError, match="inside"):
        validate_inventory([{"path": "../escape.mp4", "bytes": 1}], 1, 1)

    entries = validate_inventory(_rows(), expected_count=2, expected_bytes=7)
    with pytest.raises(VideoAcquisitionError, match="budget"):
        acquire_inventory(entries, tmp_path, max_download_bytes=6, downloader=lambda *_: None)

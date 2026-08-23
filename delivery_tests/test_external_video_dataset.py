import csv
import hashlib

import cv2
import numpy as np
import pytest

from cattle_health_app.behavior.external_clips import MANIFEST_FIELDS
from cattle_health_app.behavior.external_video_dataset import (
    ExternalVideoError,
    decode_virtual_clip,
    load_external_samples,
    measure_virtual_clip_quality,
)


def _video(path):
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (32, 32)
    )
    assert writer.isOpened()
    for index in range(20):
        frame = np.full((32, 32, 3), index * 10, np.uint8)
        frame[:, index % 24 : index % 24 + 8] = 255
        writer.write(frame)
    writer.release()


def _manifest(path, source, project_root, digest=None):
    row = {
        "sample_id": "sample-a",
        "source_group_id": "group-a",
        "dataset_id": "cbvd5",
        "dataset_version": "kaggle-version-11",
        "source_video_id": "1",
        "source_video_path": source.relative_to(project_root).as_posix(),
        "camera_id": "unknown",
        "start_second": "0.2",
        "end_second": "1.8",
        "track_id": "7",
        "source_labels": '["standing", "foraging"]',
        "mapped_label": "grazing",
        "mapping_tier": "strict",
        "crop_box": "[0.1, 0.1, 0.9, 0.9]",
        "transformations": '["virtual_time_window:1.6s"]',
        "output_path": source.relative_to(project_root).as_posix(),
        "output_sha256": digest or hashlib.sha256(source.read_bytes()).hexdigest(),
        "split": "test",
    }
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerow(row)


def test_virtual_clip_decodes_exact_model_frames_and_cvb_label(tmp_path):
    source = tmp_path / "source.mp4"
    _video(source)
    manifest = tmp_path / "manifest.csv"
    _manifest(manifest, source, tmp_path)

    sample = load_external_samples(manifest, tmp_path)[0]
    decoded = decode_virtual_clip(sample, tmp_path, frame_count=16)

    assert len(decoded.frames) == 16
    assert decoded.label_id == 1  # zero-based CVB grazing class
    assert decoded.frame_indices == tuple(sorted(decoded.frame_indices))
    assert all(frame.ndim == 3 and frame.shape[2] == 3 for frame in decoded.frames)


def test_virtual_clip_quality_is_measured_without_an_acceptance_decision(tmp_path):
    source = tmp_path / "source.mp4"
    _video(source)
    manifest = tmp_path / "manifest.csv"
    _manifest(manifest, source, tmp_path)
    decoded = decode_virtual_clip(load_external_samples(manifest, tmp_path)[0], tmp_path)

    evidence = measure_virtual_clip_quality(decoded)

    assert evidence["frame_count"] == 16
    assert 0 <= evidence["mean_brightness"] <= 1
    assert evidence["track_continuity"] == pytest.approx(1.0)
    assert "accept" not in evidence


def test_manifest_hash_mismatch_fails_before_video_decode(tmp_path):
    source = tmp_path / "source.mp4"
    _video(source)
    manifest = tmp_path / "manifest.csv"
    _manifest(manifest, source, tmp_path, digest="0" * 64)

    sample = load_external_samples(manifest, tmp_path)[0]
    with pytest.raises(ExternalVideoError, match="SHA-256"):
        decode_virtual_clip(sample, tmp_path)


def test_manifest_rejects_non_test_rows_and_escaping_paths(tmp_path):
    source = tmp_path / "source.mp4"
    _video(source)
    manifest = tmp_path / "manifest.csv"
    _manifest(manifest, source, tmp_path)
    text = manifest.read_text("utf-8")

    manifest.write_text(text.replace(",test\n", ",train\n"), encoding="utf-8")
    with pytest.raises(ExternalVideoError, match="test-only"):
        load_external_samples(manifest, tmp_path)

    manifest.write_text(text.replace("source.mp4", "../source.mp4"), encoding="utf-8")
    with pytest.raises(ExternalVideoError, match="inside project_root"):
        load_external_samples(manifest, tmp_path)

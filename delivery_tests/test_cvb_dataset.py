import csv
import json
from pathlib import Path

import cv2
import numpy as np
import pytest
import torch

from cattle_health_app.behavior.dataset import (
    CvbClipDataset,
    EXPECTED_INDEX_FIELDS,
    UnreadableClipError,
    expand_normalized_box,
    load_index,
)


FIELDS = ["sample_id", "video_id", "timestamp_seconds", "x1", "y1", "x2", "y2", "label_id", "track_id", "group_id", "frame_paths"]


def _manifest(tmp_path, **changes):
    root = tmp_path / "source"
    paths = []
    for i in range(16):
        path = root / "raw_frames" / "v1" / f"img_{i:05d}.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        image = np.zeros((60, 100, 3), np.uint8)
        image[15:45, 20:80] = (10, 20, 240)  # BGR, strongly red after conversion
        assert cv2.imwrite(str(path), image)
        paths.append(path.relative_to(root).as_posix())
    row = dict(sample_id="sample-1", video_id="v1", timestamp_seconds="2", x1="0.2", y1="0.25", x2="0.8", y2="0.75", label_id="2", track_id="7", group_id="g1", frame_paths=json.dumps(paths))
    row.update(changes)
    manifest = tmp_path / "index" / "train.csv"
    manifest.parent.mkdir()
    with manifest.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader(); writer.writerow(row)
    return manifest, root, paths


def test_dataset_returns_normalized_cthw_clip(tmp_path):
    manifest, root, _ = _manifest(tmp_path)
    sample = load_index(manifest)[0]
    assert sample.timestamp_seconds == 2.0
    clip, target = CvbClipDataset(manifest, root)[0]
    assert clip.shape == (3, 16, 224, 224)
    assert clip.dtype == torch.float32 and torch.isfinite(clip).all()
    assert target == 1
    # The crop contains the red cow and conversion is RGB, not BGR.
    unnormalized = clip[:, 0] * 0.225 + 0.45
    assert unnormalized[0].max() > 0.8
    assert unnormalized[0].max() > unnormalized[2].max() * 2


def test_expand_box_clamps_and_rejects_empty():
    assert expand_normalized_box((0, 0, .2, .4)) == pytest.approx((0, 0, .23, .46))
    with pytest.raises(ValueError):
        expand_normalized_box((.5, .5, .5, .8))


def test_letterbox_preserves_aspect_ratio_and_eval_is_deterministic(tmp_path):
    manifest, root, _ = _manifest(tmp_path, x1="0", y1="0.25", x2="1", y2="0.75")
    ds = CvbClipDataset(manifest, root, context=0)
    first, _ = ds[0]; second, _ = ds[0]
    assert torch.equal(first, second)
    image = first[:, 0] * .225 + .45
    # 100x30 crop becomes 224x67 with vertical black padding.
    assert torch.allclose(image[:, 0], torch.zeros_like(image[:, 0]), atol=.02)
    assert image[:, 112].max() > .5


class _NoFlipJitterRng:
    def random(self): return 0.0
    def uniform(self, low, high): return high


def test_training_augmentation_is_clip_consistent(tmp_path):
    manifest, root, _ = _manifest(tmp_path)
    clip, _ = CvbClipDataset(manifest, root, training=True, rng=_NoFlipJitterRng())[0]
    for t in range(1, 16):
        assert torch.equal(clip[:, 0], clip[:, t])


@pytest.mark.parametrize("change", [
    {"frame_paths": "not json"},
    {"frame_paths": json.dumps(["a.jpg"] * 16)},
    {"frame_paths": json.dumps([f"a{i}.jpg" for i in range(15)])},
    {"frame_paths": json.dumps(["C:/outside.jpg"] + [f"a{i}.jpg" for i in range(15)])},
    {"frame_paths": json.dumps(["../outside.jpg"] + [f"a{i}.jpg" for i in range(15)])},
    {"x1": "0.8", "x2": "0.2"},
    {"label_id": "13"},
])
def test_load_index_rejects_invalid_rows(tmp_path, change):
    manifest, _, _ = _manifest(tmp_path, **change)
    with pytest.raises(ValueError): load_index(manifest)


@pytest.mark.parametrize("timestamp", ["", "nan", "inf", "0", "-1", "not-a-number"])
def test_load_index_rejects_invalid_timestamp_with_field_and_row(tmp_path, timestamp):
    manifest, _, _ = _manifest(tmp_path, timestamp_seconds=timestamp)
    with pytest.raises(ValueError, match=r"row 2.*timestamp_seconds"):
        load_index(manifest)


@pytest.mark.parametrize("field", ["sample_id", "video_id", "group_id"])
def test_load_index_rejects_blank_identifiers(tmp_path, field):
    manifest, _, _ = _manifest(tmp_path, **{field: "  "})
    with pytest.raises(ValueError, match=rf"row 2.*{field}"):
        load_index(manifest)


def test_load_index_rejects_duplicate_sample_ids(tmp_path):
    manifest, _, _ = _manifest(tmp_path)
    with manifest.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    with manifest.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow(rows[0])
        writer.writerow(rows[0])
    with pytest.raises(ValueError, match=r"row 3.*sample_id"):
        load_index(manifest)


@pytest.mark.parametrize("headers", [
    FIELDS[:-1],
    FIELDS + ["extra"],
    FIELDS[:-1] + ["sample_id", "frame_paths"],
])
def test_load_index_rejects_non_exact_schema(tmp_path, headers):
    manifest, _, _ = _manifest(tmp_path)
    manifest.write_text(",".join(headers) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="schema"):
        load_index(manifest)


def test_expected_schema_matches_task2_output():
    assert list(EXPECTED_INDEX_FIELDS) == FIELDS


def test_manifest_parsing_is_lazy_but_getitem_decodes(monkeypatch, tmp_path):
    manifest, root, _ = _manifest(tmp_path)
    calls = []
    original = cv2.imread
    monkeypatch.setattr(cv2, "imread", lambda *a, **k: (calls.append(a[0]), original(*a, **k))[1])
    ds = CvbClipDataset(manifest, root)
    assert calls == []
    ds[0]
    assert len(calls) == 16


def test_missing_and_undecodable_frames_report_sample_and_path(tmp_path):
    manifest, root, paths = _manifest(tmp_path)
    missing = root / paths[3]
    missing.unlink()
    with pytest.raises(UnreadableClipError, match=r"sample-1.*img_00003"):
        CvbClipDataset(manifest, root)[0]
    missing.write_bytes(b"not a jpeg")
    with pytest.raises(UnreadableClipError, match=r"sample-1.*img_00003"):
        CvbClipDataset(manifest, root)[0]


def test_symlink_escape_rejected_before_decode(monkeypatch, tmp_path):
    manifest, root, paths = _manifest(tmp_path)
    external = tmp_path / "external.jpg"; external.write_bytes((root / paths[0]).read_bytes())
    link = root / paths[0]; link.unlink()
    try: link.symlink_to(external)
    except OSError: pytest.skip("symlink privilege unavailable")
    monkeypatch.setattr(cv2, "imread", lambda *_: pytest.fail("must reject before decode"))
    with pytest.raises(UnreadableClipError, match=r"sample-1.*img_00000"):
        CvbClipDataset(manifest, root)[0]

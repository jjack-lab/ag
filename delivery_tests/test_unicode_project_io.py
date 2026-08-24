from __future__ import annotations

from threading import Lock
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
import torch

import cattle_health_app.media_processor as media_processor_module
from cattle_health_app.image_io import read_cv_image, write_cv_image
from cattle_health_app.media_processor import LocalMediaProcessor
from delivery_tests.io_helpers import (
    save_torch_fixture,
    write_cv_image_fixture,
)


def test_torch_fixture_round_trips_below_unicode_directory(tmp_path):
    path = tmp_path / "牛只夹具" / "payload.pt"

    save_torch_fixture(path, {"value": torch.tensor([1, 2, 3])})

    assert path.is_file()
    with path.open("rb") as handle:
        loaded = torch.load(handle, map_location="cpu")
    assert torch.equal(loaded["value"], torch.tensor([1, 2, 3]))


def test_cv_fixture_round_trips_below_unicode_directory(tmp_path):
    path = tmp_path / "牛只夹具" / "frame.jpg"
    image = np.full((12, 16, 3), (10, 80, 220), dtype=np.uint8)

    write_cv_image_fixture(path, image)

    encoded = np.frombuffer(path.read_bytes(), dtype=np.uint8)
    decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    assert decoded is not None
    assert decoded.shape == image.shape
    assert np.abs(decoded.astype(np.int16) - image.astype(np.int16)).mean() < 5


def test_product_image_round_trips_below_unicode_directory(tmp_path):
    path = tmp_path / "牛只产品图像" / "annotated.png"
    image = np.full((10, 14, 3), (20, 100, 240), dtype=np.uint8)

    written = write_cv_image(path, image)
    decoded = read_cv_image(path, cv2.IMREAD_COLOR)

    assert written == path
    assert path.is_file()
    assert decoded is not None
    assert np.array_equal(decoded, image)


@pytest.mark.parametrize("kind", ["missing", "empty", "invalid"])
def test_product_image_reader_returns_none_for_unreadable_input(tmp_path, kind):
    path = tmp_path / "牛只产品图像" / f"{kind}.jpg"
    if kind == "empty":
        path.parent.mkdir(parents=True)
        path.write_bytes(b"")
    elif kind == "invalid":
        path.parent.mkdir(parents=True)
        path.write_bytes(b"not-an-image")

    assert read_cv_image(path, cv2.IMREAD_COLOR) is None


def test_product_image_writer_rejects_extensionless_target(tmp_path):
    path = tmp_path / "牛只产品图像" / "annotated"

    with pytest.raises(ValueError, match="extension"):
        write_cv_image(path, np.zeros((2, 2, 3), dtype=np.uint8))

    assert not path.exists()


def _processor_without_registry_initialization():
    processor = object.__new__(LocalMediaProcessor)
    processor._inference_lock = Lock()
    processor._load_model = lambda: object()
    return processor


def test_local_media_processor_writes_unicode_result_path(tmp_path, monkeypatch):
    frame = np.full((8, 9, 3), (25, 125, 225), dtype=np.uint8)
    monkeypatch.setattr(
        media_processor_module,
        "detect_image",
        lambda *args: SimpleNamespace(annotated_frame=frame, detection_count=3),
    )
    result_path = tmp_path / "牛只识别结果" / "annotated.png"

    count = _processor_without_registry_initialization().detect_image(
        tmp_path / "source.png", result_path, 0.25, 0.45, 1
    )

    assert count == 3
    assert np.array_equal(read_cv_image(result_path), frame)


@pytest.mark.parametrize("error", [OSError("disk denied"), ValueError("encode failed")])
def test_local_media_processor_translates_unicode_writer_errors(
    tmp_path, monkeypatch, error
):
    monkeypatch.setattr(
        media_processor_module,
        "detect_image",
        lambda *args: SimpleNamespace(
            annotated_frame=np.zeros((2, 2, 3), dtype=np.uint8),
            detection_count=1,
        ),
    )
    monkeypatch.setattr(
        media_processor_module,
        "write_cv_image",
        lambda *args: (_ for _ in ()).throw(error),
    )

    with pytest.raises(ValueError, match="无法保存识别结果") as caught:
        _processor_without_registry_initialization().detect_image(
            tmp_path / "source.png",
            tmp_path / "牛只识别结果" / "annotated.png",
            0.25,
            0.45,
            1,
        )

    assert caught.value.__cause__ is error

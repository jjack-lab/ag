from __future__ import annotations

import cv2
import numpy as np
import pytest
import torch

from cattle_health_app.image_io import read_cv_image, write_cv_image
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

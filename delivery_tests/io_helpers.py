from __future__ import annotations

from pathlib import Path

import cv2
import torch


def save_torch_fixture(path: str | Path, payload) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as handle:
        torch.save(payload, handle)
    return destination


def write_cv_image_fixture(path: str | Path, image) -> Path:
    destination = Path(path)
    extension = destination.suffix.lower()
    if not extension:
        raise ValueError("Image fixture path requires a file extension")
    encoded_ok, encoded = cv2.imencode(extension, image)
    if not encoded_ok:
        raise ValueError(f"Unable to encode image fixture: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(encoded.tobytes())
    return destination

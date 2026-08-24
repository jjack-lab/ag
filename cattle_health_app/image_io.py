"""Unicode-safe OpenCV image I/O backed by Python file APIs."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def read_cv_image(path: str | Path, flags: int = cv2.IMREAD_COLOR):
    """Decode an image without passing a Unicode path to OpenCV's file API."""
    try:
        payload = Path(path).read_bytes()
    except OSError:
        return None
    if not payload:
        return None
    try:
        return cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), flags)
    except (cv2.error, ValueError):
        return None


def write_cv_image(path: str | Path, image: np.ndarray) -> Path:
    """Encode and write an image without passing a Unicode path to OpenCV."""
    target = Path(path)
    extension = target.suffix.lower()
    if not extension:
        raise ValueError("image target must include a file extension")
    try:
        encoded, buffer = cv2.imencode(extension, image)
    except cv2.error as exc:
        raise ValueError(f"cannot encode image as {extension}") from exc
    if not encoded:
        raise ValueError(f"cannot encode image as {extension}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(buffer.tobytes())
    return target

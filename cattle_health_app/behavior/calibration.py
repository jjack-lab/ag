"""Validated runtime loading for behavior calibration artifacts."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Union

from cattle_health_app.model_registry import sha256_file

PathLike = Union[str, os.PathLike]


@dataclass(frozen=True)
class BehaviorCalibration:
    temperature: float
    min_confidence: float
    max_normalized_entropy: float
    model_version: str
    checkpoint_sha256: str


def _finite_number(value, field: str, *, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite number")
    result = float(value)
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise ValueError(f"{field} must be in [{minimum}, {maximum}]")
    return result


def load_behavior_calibration(
    path: PathLike,
    *,
    checkpoint_path: PathLike,
    model_version: str,
) -> BehaviorCalibration:
    """Load an experiment artifact only when it belongs to the active model."""
    artifact_path = Path(path).expanduser().resolve()
    try:
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read behavior calibration artifact: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("behavior calibration schema_version must be 1")
    artifact_version = payload.get("model_version")
    if artifact_version != model_version:
        raise ValueError(
            "behavior calibration model version mismatch: "
            f"expected {model_version!r}, got {artifact_version!r}"
        )
    expected_hash = payload.get("checkpoint_sha256")
    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        raise ValueError("checkpoint_sha256 must be a 64-character string")
    actual_hash = sha256_file(Path(checkpoint_path).expanduser().resolve())
    if actual_hash != expected_hash:
        raise ValueError(
            "behavior calibration checkpoint SHA-256 mismatch: "
            f"expected {expected_hash}, got {actual_hash}"
        )
    if payload.get("selection_split") != "validation":
        raise ValueError("behavior calibration must be selected on validation data")
    policy = payload.get("policy")
    if not isinstance(policy, dict) or policy.get("selection_split") != "validation":
        raise ValueError("behavior rejection policy must be selected on validation data")
    temperature = _finite_number(
        payload.get("temperature"), "temperature", minimum=1e-12, maximum=1e6
    )
    min_confidence = _finite_number(
        policy.get("min_confidence"), "min_confidence", minimum=0.0, maximum=1.0
    )
    max_entropy = _finite_number(
        policy.get("max_normalized_entropy"),
        "max_normalized_entropy",
        minimum=0.0,
        maximum=1.0,
    )
    return BehaviorCalibration(
        temperature=temperature,
        min_confidence=min_confidence,
        max_normalized_entropy=max_entropy,
        model_version=artifact_version,
        checkpoint_sha256=expected_hash,
    )


def default_calibration_path(checkpoint_path: PathLike) -> Path:
    checkpoint = Path(checkpoint_path).expanduser().resolve()
    configured = os.environ.get("AGRINEBULA_BEHAVIOR_CALIBRATION")
    if configured:
        return Path(configured).expanduser().resolve()
    stem = checkpoint.stem
    if stem.endswith("_best"):
        stem = stem[:-len("_best")]
    return checkpoint.with_name(f"{stem}_calibration.json")

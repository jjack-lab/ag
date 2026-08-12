from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path


class ModelNotFoundError(FileNotFoundError):
    """Raised when the packaged delivery detector cannot be resolved."""


class ModelIntegrityError(ValueError):
    """Raised when the packaged delivery detector has an unexpected hash."""


EXPECTED_DELIVERY_MODEL_SHA256 = (
    "46d734cba7553f31e89e739156f50e9a675b176f798c70159838497531771a64"
)


@dataclass(frozen=True)
class ModelArtifact:
    name: str
    path: Path
    sha256: str

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["path"] = str(self.path)
        return payload


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_detector_model(
    explicit_path: str | Path | None = None,
    project_root: str | Path | None = None,
) -> ModelArtifact:
    root = Path(project_root or Path(__file__).resolve().parents[1])
    configured = explicit_path or os.environ.get("AGRINEBULA_DETECTOR_MODEL")
    path = (
        Path(configured)
        if configured
        else root / "models" / "detection" / "yolo11s-waid.pt"
    )
    path = path.expanduser().resolve()
    if not path.is_file():
        raise ModelNotFoundError(
            f"YOLO11 detector weight is missing: {path}. "
            "Set AGRINEBULA_DETECTOR_MODEL or copy the delivery weight."
        )
    fingerprint = sha256_file(path)
    if not configured and fingerprint != EXPECTED_DELIVERY_MODEL_SHA256:
        raise ModelIntegrityError(
            "Packaged YOLO11 detector SHA-256 mismatch: "
            f"expected {EXPECTED_DELIVERY_MODEL_SHA256}, got {fingerprint}."
        )
    return ModelArtifact(
        name="yolo11-detector",
        path=path,
        sha256=fingerprint,
    )

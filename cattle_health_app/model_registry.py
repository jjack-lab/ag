from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path


class ModelNotFoundError(FileNotFoundError):
    """Raised when the packaged delivery detector cannot be resolved."""


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
    return ModelArtifact(
        name="yolo11-detector",
        path=path,
        sha256=sha256_file(path),
    )

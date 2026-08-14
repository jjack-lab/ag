"""X3D model construction and versioned behavior checkpoints.

Checkpoints use ``torch.save``.  On runtimes supporting restricted loading we
request ``weights_only=True``.  Older runtimes cannot safely deserialize an
untrusted pickle, so loading there fails explicitly instead of silently
crossing that trust boundary.
"""

from __future__ import annotations

import inspect
import math
import os
import pickle
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional, Set, Tuple, Union

import torch
from torch import nn
from pytorchvideo.models.hub import x3d_xs as _x3d_xs

from .cvb_labels import CVB_LABELS

FORMAT_VERSION = 1
ARCHITECTURE = "x3d_xs"
INPUT_FRAMES = 16
INPUT_SIZE = 224
DEFAULT_MODEL_VERSION = "cvb-x3d-v1"
LABEL_ORDER: Tuple[str, ...] = tuple(CVB_LABELS[i].name for i in range(1, 13))
CHECKPOINT_FIELDS = frozenset(
    {
        "format_version", "architecture", "labels", "input_frames",
        "input_size", "model_version", "state_dict", "metrics",
        "training_config",
    }
)
PathLike = Union[str, os.PathLike]

JSONScalar = Union[None, bool, int, float, str]
FrozenJSON = Union[JSONScalar, Tuple["FrozenJSON", ...], Mapping[str, "FrozenJSON"]]

@dataclass(frozen=True)
class BehaviorCheckpointMetadata:
    format_version: int
    architecture: str
    labels: Tuple[str, ...]
    input_frames: int
    input_size: int
    model_version: str
    metrics: Mapping[str, FrozenJSON]
    training_config: Mapping[str, FrozenJSON]


@dataclass(frozen=True)
class LoadedBehaviorCheckpoint:
    model: nn.Module
    metadata: BehaviorCheckpointMetadata


def build_x3d(num_classes: int = 12, pretrained: bool = True) -> nn.Module:
    """Construct X3D-XS and replace only its final classifier projection."""
    if isinstance(num_classes, bool) or not isinstance(num_classes, int) or num_classes <= 0:
        raise ValueError("num_classes must be a positive integer")
    model = _x3d_xs(pretrained=pretrained)
    projection = model.blocks[-1].proj
    if not isinstance(projection, nn.Linear):
        raise RuntimeError("unsupported X3D-XS classifier projection")
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(0)
        replacement = nn.Linear(
            projection.in_features,
            num_classes,
            bias=projection.bias is not None,
            device=projection.weight.device,
            dtype=projection.weight.dtype,
        )
    model.blocks[-1].proj = replacement
    return model


def _validate_json(
    value: Any, field: str, path: str, active: Optional[Set[int]] = None
) -> Any:
    if active is None:
        active = set()
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        raise ValueError(f"{field} must contain JSON-compatible finite numbers at {path}")
    if isinstance(value, (Mapping, list, tuple)):
        identity = id(value)
        if identity in active:
            raise ValueError(f"{field} metadata at {path} contains a cycle")
        active.add(identity)
        try:
            if isinstance(value, Mapping):
                result = {}
                for key, item in value.items():
                    if not isinstance(key, str):
                        raise ValueError(
                            f"{field} must contain JSON-compatible string keys at {path}"
                        )
                    result[key] = _validate_json(item, field, f"{path}.{key}", active)
                return result
            return [
                _validate_json(item, field, f"{path}[{index}]", active)
                for index, item in enumerate(value)
            ]
        finally:
            active.remove(identity)
    raise ValueError(f"{field} must contain JSON-compatible values at {path}")


def _json_mapping(value: Any, field: str) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a mapping")
    return _validate_json(value, field, field)


def _freeze_json(value: Any) -> FrozenJSON:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    return value


def _cpu_state_dict(model: nn.Module) -> Dict[str, torch.Tensor]:
    return {name: tensor.detach().cpu().clone() for name, tensor in model.state_dict().items()}


def save_behavior_checkpoint(
    path: PathLike,
    model: nn.Module,
    metrics: Mapping[str, Any],
    training_config: Mapping[str, Any],
    model_version: str = DEFAULT_MODEL_VERSION,
) -> None:
    """Atomically save a CPU-portable behavior checkpoint."""
    if not isinstance(model_version, str) or not model_version.strip():
        raise ValueError("model_version must be a nonempty string")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "format_version": FORMAT_VERSION,
        "architecture": ARCHITECTURE,
        "labels": list(LABEL_ORDER),
        "input_frames": INPUT_FRAMES,
        "input_size": INPUT_SIZE,
        "model_version": model_version,
        "state_dict": _cpu_state_dict(model),
        "metrics": _json_mapping(metrics, "metrics"),
        "training_config": _json_mapping(training_config, "training_config"),
    }
    temporary = None
    try:
        handle = tempfile.NamedTemporaryFile(
            mode="w+b", prefix=f".{destination.name}.", suffix=".tmp",
            dir=str(destination.parent), delete=False,
        )
        temporary = Path(handle.name)
        with handle:
            torch.save(payload, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def _validate_payload(payload: Any) -> BehaviorCheckpointMetadata:
    if not isinstance(payload, Mapping):
        raise ValueError("checkpoint payload must be a mapping")
    fields = set(payload)
    if fields != CHECKPOINT_FIELDS:
        missing = sorted(CHECKPOINT_FIELDS - fields)
        extra = sorted(fields - CHECKPOINT_FIELDS)
        raise ValueError(f"checkpoint fields are invalid (missing={missing}, extra={extra})")
    if type(payload["format_version"]) is not int or payload["format_version"] != FORMAT_VERSION:
        raise ValueError(f"format_version must be {FORMAT_VERSION}")
    if payload["architecture"] != ARCHITECTURE:
        raise ValueError(f"architecture must be {ARCHITECTURE!r}")
    labels = payload["labels"]
    if not isinstance(labels, (list, tuple)) or tuple(labels) != LABEL_ORDER:
        raise ValueError("labels must match the immutable CVB label order")
    if type(payload["input_frames"]) is not int or payload["input_frames"] != INPUT_FRAMES:
        raise ValueError(f"input_frames must be {INPUT_FRAMES}")
    if type(payload["input_size"]) is not int or payload["input_size"] != INPUT_SIZE:
        raise ValueError(f"input_size must be {INPUT_SIZE}")
    version = payload["model_version"]
    if not isinstance(version, str) or not version.strip():
        raise ValueError("model_version must be a nonempty string")
    metrics = _json_mapping(payload["metrics"], "metrics")
    config = _json_mapping(payload["training_config"], "training_config")
    state = payload["state_dict"]
    if not isinstance(state, Mapping) or not state:
        raise ValueError("state_dict must be a nonempty mapping")
    if any(not isinstance(k, str) or not isinstance(v, torch.Tensor) for k, v in state.items()):
        raise ValueError("state_dict must map string names to tensors")
    return BehaviorCheckpointMetadata(
        FORMAT_VERSION, ARCHITECTURE, LABEL_ORDER, INPUT_FRAMES, INPUT_SIZE,
        version, _freeze_json(metrics), _freeze_json(config),
    )


def _safe_torch_load(path: Path, device: torch.device) -> Any:
    parameters = inspect.signature(torch.load).parameters
    if "weights_only" not in parameters:
        raise RuntimeError(
            "this PyTorch version cannot safely load untrusted checkpoints; "
            "upgrade to a version supporting torch.load(weights_only=True)"
        )
    try:
        return torch.load(path, map_location=device, weights_only=True)
    except (pickle.UnpicklingError, EOFError, RuntimeError, ValueError) as error:
        raise ValueError(
            "could not safely load checkpoint; payload may contain non JSON-compatible "
            f"metadata or invalid tensor data: {error}"
        ) from error


def _validate_device(device: Union[str, torch.device]) -> torch.device:
    try:
        validated = torch.device(device)
    except (TypeError, ValueError, RuntimeError) as error:
        raise ValueError(f"invalid behavior model device {device!r}: {error}") from error
    if validated.type == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA device requested but CUDA is unavailable")
        if validated.index is not None and validated.index >= torch.cuda.device_count():
            raise RuntimeError(
                f"CUDA device index {validated.index} is unavailable; "
                f"only {torch.cuda.device_count()} device(s) detected"
            )
    return validated


def load_behavior_checkpoint(
    path: PathLike, device: Union[str, torch.device] = "cpu"
) -> LoadedBehaviorCheckpoint:
    """Safely validate, strictly restore, move and evaluate a checkpoint."""
    checkpoint_path = Path(path)
    if not checkpoint_path.exists():
        raise FileNotFoundError(checkpoint_path)
    if not checkpoint_path.is_file():
        raise ValueError(f"checkpoint path is not a regular file: {checkpoint_path}")
    validated_device = _validate_device(device)
    payload = _safe_torch_load(checkpoint_path, torch.device("cpu"))
    metadata = _validate_payload(payload)
    model = build_x3d(num_classes=len(LABEL_ORDER), pretrained=False)
    try:
        model.load_state_dict(payload["state_dict"], strict=True)
    except RuntimeError as error:
        raise ValueError(f"checkpoint state_dict is incompatible: {error}") from error
    model.to(validated_device)
    model.eval()
    return LoadedBehaviorCheckpoint(model=model, metadata=metadata)

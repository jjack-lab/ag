"""Portable WAID4500 dataset and training reproducibility helpers."""

from __future__ import annotations

import csv
import filecmp
import hashlib
import io
import json
import os
import platform
import re
import shutil
import sys
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

import yaml


CLASS_NAMES = {
    0: "sheep",
    1: "cattle",
    2: "seal",
    3: "camelus",
    4: "kiang",
    5: "zebra",
}
MANIFEST_FIELDS = (
    "split",
    "output_image",
    "output_label",
    "source_image",
    "source_label",
    "source_split",
    "class_id",
    "class_name",
    "instances",
    "group_id",
)
SPLITS = ("train", "valid", "test")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
PRODUCTION_MODEL_SHA256 = "46d734cba7553f31e89e739156f50e9a675b176f798c70159838497531771a64"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ManifestError(ValueError):
    """Raised when frozen WAID evidence violates its data contract."""


@dataclass(frozen=True)
class ManifestRow:
    split: str
    output_image: PurePosixPath
    output_label: PurePosixPath
    source_split: str
    source_image_name: str
    source_label_name: str
    class_id: int
    class_name: str
    instances: int
    group_id: str


@dataclass(frozen=True)
class ImportSources:
    raw: Path
    frozen_dataset: Path
    pretrained: Path
    run: Path
    logs: Path


def _parse_relative_output(value: str, kind: str, split: str) -> PurePosixPath:
    if not value or "\\" in value or ":" in value:
        raise ManifestError("{} path is not canonical".format(kind))
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value:
        raise ManifestError("{} path is not relative POSIX".format(kind))
    if any(part in ("", ".", "..") for part in path.parts):
        raise ManifestError("{} path escapes its output root".format(kind))

    prefix = "images" if kind == "image" else "labels"
    if len(path.parts) != 3 or path.parts[:2] != (prefix, split):
        raise ManifestError("{} path does not match split".format(kind))
    if kind == "image" and path.suffix.casefold() not in IMAGE_SUFFIXES:
        raise ManifestError("image path has unsupported extension")
    if kind == "label" and path.suffix.casefold() != ".txt":
        raise ManifestError("label path must end in .txt")
    return path


def _canonical_int(value: str, field: str, minimum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ManifestError("{} must be an integer".format(field)) from exc
    if parsed < minimum or str(parsed) != str(value).strip():
        raise ManifestError("{} must be an integer >= {}".format(field, minimum))
    return parsed


def _source_name(value: str, kind: str) -> str:
    name = PureWindowsPath(value).name
    if not name or name in (".", ".."):
        raise ManifestError("{} source path has no file name".format(kind))
    return name


def load_manifest(path: Path) -> List[ManifestRow]:
    """Load and strictly validate the frozen WAID4500 selection manifest."""

    manifest_path = Path(path)
    try:
        handle = manifest_path.open("r", encoding="utf-8-sig", newline="")
    except OSError as exc:
        raise ManifestError("cannot read manifest: {}".format(manifest_path)) from exc

    rows = []
    seen_images = set()
    seen_labels = set()
    with handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != MANIFEST_FIELDS:
            raise ManifestError("manifest has unexpected columns")
        for line_number, raw in enumerate(reader, start=2):
            try:
                split = str(raw["split"]).strip()
                source_split = str(raw["source_split"]).strip()
                if split not in SPLITS or source_split not in SPLITS:
                    raise ManifestError("unsupported split")

                output_image = _parse_relative_output(
                    str(raw["output_image"]).strip(), "image", split
                )
                output_label = _parse_relative_output(
                    str(raw["output_label"]).strip(), "label", split
                )
                if output_image in seen_images or output_label in seen_labels:
                    raise ManifestError("duplicate output path")

                class_id = _canonical_int(str(raw["class_id"]).strip(), "class_id", 0)
                if class_id not in CLASS_NAMES:
                    raise ManifestError("class_id is outside the supported range")
                class_name = str(raw["class_name"]).strip()
                if class_name != CLASS_NAMES[class_id]:
                    raise ManifestError("class_name does not match class_id")
                instances = _canonical_int(str(raw["instances"]).strip(), "instances", 1)
                group_id = str(raw["group_id"]).strip()
                if not group_id:
                    raise ManifestError("group_id must not be empty")

                row = ManifestRow(
                    split=split,
                    output_image=output_image,
                    output_label=output_label,
                    source_split=source_split,
                    source_image_name=_source_name(str(raw["source_image"]), "image"),
                    source_label_name=_source_name(str(raw["source_label"]), "label"),
                    class_id=class_id,
                    class_name=class_name,
                    instances=instances,
                    group_id=group_id,
                )
            except ManifestError as exc:
                raise ManifestError("manifest row {}: {}".format(line_number, exc)) from exc
            rows.append(row)
            seen_images.add(output_image)
            seen_labels.add(output_label)

    if not rows:
        raise ManifestError("manifest must contain at least one row")
    return rows


def parse_label(content: bytes) -> Tuple[int, int]:
    """Validate YOLO labels and return their single class plus instance count."""

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ManifestError("label is not valid UTF-8") from exc

    class_ids = set()
    instances = 0
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 5:
            raise ManifestError("label line {} must contain five fields".format(line_number))
        try:
            values = [Decimal(field) for field in fields]
        except (InvalidOperation, ValueError) as exc:
            raise ManifestError("label line {} is not numeric".format(line_number)) from exc
        if any(not value.is_finite() for value in values):
            raise ManifestError("label line {} contains a non-finite value".format(line_number))
        class_value = values[0]
        if class_value != class_value.to_integral_value():
            raise ManifestError("label line {} class must be integral".format(line_number))
        class_id = int(class_value)
        if class_id not in CLASS_NAMES:
            raise ManifestError("label line {} class is unsupported".format(line_number))
        if any(value < Decimal(0) or value > Decimal(1) for value in values[1:]):
            raise ManifestError("label line {} coordinate is outside [0, 1]".format(line_number))
        class_ids.add(class_id)
        instances += 1

    if instances == 0:
        raise ManifestError("label must contain at least one instance")
    if len(class_ids) != 1:
        raise ManifestError("each WAID image must contain exactly one class")
    return next(iter(class_ids)), instances


def split_counts(rows: Iterable[ManifestRow]) -> Dict[str, int]:
    counts = {split: 0 for split in SPLITS}
    for row in rows:
        counts[row.split] += 1
    return counts


def _safe_child(root: Path, relative: Path) -> Path:
    resolved_root = Path(root).expanduser().resolve()
    candidate = (resolved_root / relative).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ManifestError("path escapes configured root: {}".format(relative)) from exc
    return candidate


def _remove_staging(staging: Path, output_root: Path) -> None:
    resolved_staging = staging.resolve()
    resolved_parent = output_root.parent.resolve()
    prefix = ".{}.staging-".format(output_root.name)
    if resolved_staging.parent != resolved_parent or not resolved_staging.name.startswith(prefix):
        raise RuntimeError("refusing to remove unexpected staging path")
    if resolved_staging.exists():
        shutil.rmtree(str(resolved_staging))


def _validate_group_isolation(rows: Iterable[ManifestRow]) -> None:
    group_splits = {}
    for row in rows:
        group = row.group_id.casefold()
        previous = group_splits.setdefault(group, row.split)
        if previous != row.split:
            raise ManifestError("group_id appears in multiple splits: {}".format(row.group_id))


def rebuild_dataset(
    raw_root: Path,
    manifest_path: Path,
    output_root: Path,
    expected_counts: Optional[Mapping[str, int]] = None,
) -> Dict[str, object]:
    """Materialize the frozen manifest from raw WAID files atomically."""

    raw = Path(raw_root).expanduser().resolve()
    output = Path(output_root).expanduser().resolve()
    if output.exists():
        raise FileExistsError("output already exists: {}".format(output))
    if not output.parent.is_dir():
        raise FileNotFoundError("output parent not found: {}".format(output.parent))

    rows = load_manifest(Path(manifest_path))
    counts = split_counts(rows)
    if expected_counts is not None:
        normalized = {split: int(expected_counts.get(split, 0)) for split in SPLITS}
        if counts != normalized:
            raise ManifestError(
                "split counts do not match expected values: actual={}, expected={}".format(
                    counts, normalized
                )
            )
    _validate_group_isolation(rows)

    staging = Path(
        tempfile.mkdtemp(prefix=".{}.staging-".format(output.name), dir=str(output.parent))
    ).resolve()
    try:
        for split in SPLITS:
            (staging / "images" / split).mkdir(parents=True)
            (staging / "labels" / split).mkdir(parents=True)
        (staging / "splits").mkdir()
        (staging / "reports").mkdir()

        split_lines = {split: [] for split in SPLITS}
        for row in rows:
            source_image = _safe_child(
                raw, Path("images") / row.source_split / row.source_image_name
            )
            source_label = _safe_child(
                raw, Path("labels") / row.source_split / row.source_label_name
            )
            if not source_image.is_file():
                raise ManifestError("source image not found: {}".format(source_image))
            if not source_label.is_file():
                raise ManifestError("source label not found: {}".format(source_label))
            class_id, instances = parse_label(source_label.read_bytes())
            if class_id != row.class_id or instances != row.instances:
                raise ManifestError(
                    "label metadata does not match manifest: {}".format(source_label.name)
                )

            destination_image = _safe_child(staging, Path(row.output_image.as_posix()))
            destination_label = _safe_child(staging, Path(row.output_label.as_posix()))
            shutil.copy2(source_image, destination_image)
            shutil.copy2(source_label, destination_label)
            split_lines[row.split].append(row.output_image.as_posix())

        for split in SPLITS:
            (staging / "splits" / "{}.txt".format(split)).write_text(
                "".join("{}\n".format(line) for line in split_lines[split]),
                encoding="utf-8",
            )

        write_runtime_data_yaml(output, staging / "data.yaml")
        shutil.copy2(Path(manifest_path), staging / "reports" / "dataset_manifest.csv")
        summary = {
            "status": "complete",
            "splits": counts,
            "total_images": sum(counts.values()),
            "total_labels": sum(counts.values()),
            "classes": len(CLASS_NAMES),
            "class_names": [CLASS_NAMES[index] for index in sorted(CLASS_NAMES)],
        }
        (staging / "reports" / "generation_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        if output.exists():
            raise FileExistsError("output appeared during generation: {}".format(output))
        staging.rename(output)
        return summary
    except BaseException:
        _remove_staging(staging, output)
        raise


def validate_dataset(
    raw_root: Path,
    manifest_path: Path,
    output_root: Path,
    expected_counts: Optional[Mapping[str, int]] = None,
) -> Dict[str, object]:
    """Validate a materialized dataset against raw data and its frozen manifest."""

    raw = Path(raw_root).expanduser().resolve()
    output = Path(output_root).expanduser().resolve()
    if not output.is_dir():
        raise ManifestError("dataset output not found: {}".format(output))
    rows = load_manifest(Path(manifest_path))
    counts = split_counts(rows)
    if expected_counts is not None:
        normalized = {split: int(expected_counts.get(split, 0)) for split in SPLITS}
        if counts != normalized:
            raise ManifestError(
                "split counts do not match expected values: actual={}, expected={}".format(
                    counts, normalized
                )
            )
    _validate_group_isolation(rows)

    expected_split_lines = {split: [] for split in SPLITS}
    for row in rows:
        source_image = _safe_child(
            raw, Path("images") / row.source_split / row.source_image_name
        )
        source_label = _safe_child(
            raw, Path("labels") / row.source_split / row.source_label_name
        )
        output_image = _safe_child(output, Path(row.output_image.as_posix()))
        output_label = _safe_child(output, Path(row.output_label.as_posix()))
        for path, description in (
            (source_image, "source image"),
            (source_label, "source label"),
            (output_image, "output image"),
            (output_label, "output label"),
        ):
            if not path.is_file():
                raise ManifestError("{} not found: {}".format(description, path))
        class_id, instances = parse_label(output_label.read_bytes())
        if class_id != row.class_id or instances != row.instances:
            raise ManifestError("output label metadata does not match manifest")
        if not filecmp.cmp(str(source_image), str(output_image), shallow=False):
            raise ManifestError("output image differs from raw source")
        if not filecmp.cmp(str(source_label), str(output_label), shallow=False):
            raise ManifestError("output label differs from raw source")
        expected_split_lines[row.split].append(row.output_image.as_posix())

    for split in SPLITS:
        split_path = output / "splits" / "{}.txt".format(split)
        if not split_path.is_file():
            raise ManifestError("split list not found: {}".format(split_path))
        actual_lines = split_path.read_text(encoding="utf-8-sig").splitlines()
        if actual_lines != expected_split_lines[split]:
            raise ManifestError("{} split list differs from manifest".format(split))

    try:
        data_yaml = yaml.safe_load((output / "data.yaml").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ManifestError("cannot read dataset data.yaml") from exc
    expected_yaml = {
        "path": str(output),
        "train": "images/train",
        "val": "images/valid",
        "test": "images/test",
        "names": dict(CLASS_NAMES),
    }
    if data_yaml != expected_yaml:
        raise ManifestError("data.yaml does not match the portable dataset contract")

    return {
        "status": "complete",
        "splits": counts,
        "total_images": sum(counts.values()),
        "total_labels": sum(counts.values()),
        "classes": len(CLASS_NAMES),
        "class_names": [CLASS_NAMES[index] for index in sorted(CLASS_NAMES)],
    }


def _inventory(path: Path) -> Dict[str, int]:
    if path.is_file():
        return {"files": 1, "bytes": path.stat().st_size}
    files = [candidate for candidate in path.rglob("*") if candidate.is_file()]
    return {
        "files": len(files),
        "bytes": sum(candidate.stat().st_size for candidate in files),
    }


def _require_import_sources(sources: ImportSources) -> None:
    required = (
        (sources.raw / "images", "raw images"),
        (sources.raw / "labels", "raw labels"),
        (sources.frozen_dataset / "data.yaml", "frozen data.yaml"),
        (
            sources.frozen_dataset / "reports" / "generation_summary.json",
            "frozen generation summary",
        ),
        (sources.pretrained, "pretrained checkpoint"),
        (sources.run / "weights" / "best.pt", "archived best checkpoint"),
        (sources.run / "results.csv", "archived results"),
        (sources.logs, "training logs"),
    )
    for path, description in required:
        if not path.exists():
            raise FileNotFoundError("{} not found: {}".format(description, path))


def _copy_asset(source: Path, destination: Path, replace: bool) -> Dict[str, int]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage_root = Path(
        tempfile.mkdtemp(prefix=".{}-import-".format(destination.name), dir=destination.parent)
    )
    staged = stage_root / destination.name
    backup = destination.parent / ".{}-backup-{}".format(
        destination.name, uuid.uuid4().hex
    )
    try:
        if source.is_dir():
            shutil.copytree(str(source), str(staged))
        else:
            shutil.copy2(str(source), str(staged))
        source_inventory = _inventory(source)
        staged_inventory = _inventory(staged)
        if staged_inventory != source_inventory:
            raise IOError("staged asset inventory does not match source")

        moved_existing = False
        if destination.exists():
            if not replace:
                raise FileExistsError("destination already exists: {}".format(destination))
            destination.rename(backup)
            moved_existing = True
        try:
            staged.rename(destination)
        except BaseException:
            if moved_existing and not destination.exists() and backup.exists():
                backup.rename(destination)
            raise
        if moved_existing and backup.exists():
            if backup.is_dir():
                shutil.rmtree(str(backup))
            else:
                backup.unlink()
        return source_inventory
    finally:
        if stage_root.exists():
            shutil.rmtree(str(stage_root))


def import_assets(
    sources: ImportSources, project_root: Path, replace: bool = False
) -> Dict[str, object]:
    """Copy external WAID assets into ignored, fixed local destinations."""

    normalized = ImportSources(
        raw=Path(sources.raw).expanduser().resolve(),
        frozen_dataset=Path(sources.frozen_dataset).expanduser().resolve(),
        pretrained=Path(sources.pretrained).expanduser().resolve(),
        run=Path(sources.run).expanduser().resolve(),
        logs=Path(sources.logs).expanduser().resolve(),
    )
    _require_import_sources(normalized)
    root = Path(project_root).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError("project root not found: {}".format(root))

    destinations = {
        "raw": _safe_child(root, Path("data/external/waid/raw")),
        "frozen_dataset": _safe_child(
            root, Path("data/external/waid/derived/waid4500_v1")
        ),
        "pretrained": _safe_child(root, Path("data/external/waid/cache/yolo11s.pt")),
        "run": _safe_child(root, Path("outputs/training/waid4500_yolo11s/run")),
        "logs": _safe_child(root, Path("outputs/training/waid4500_yolo11s/logs")),
    }
    source_map = {
        "raw": normalized.raw,
        "frozen_dataset": normalized.frozen_dataset,
        "pretrained": normalized.pretrained,
        "run": normalized.run,
        "logs": normalized.logs,
    }
    if not replace:
        existing = [str(path) for path in destinations.values() if path.exists()]
        if existing:
            raise FileExistsError("destination already exists: {}".format(existing[0]))

    components = {}
    for name in ("raw", "frozen_dataset", "pretrained", "run", "logs"):
        source = source_map[name]
        destination = destinations[name]
        if source == destination or source in destination.parents or destination in source.parents:
            raise ValueError("source and destination must not overlap: {}".format(name))
        inventory = _copy_asset(source, destination, replace)
        if name == "frozen_dataset":
            # The imported data.yaml keeps the source machine's absolute root
            # (in this project an old E: drive path), which cannot work here.
            write_runtime_data_yaml(destination, destination / "data.yaml")
            inventory = _inventory(destination)
        components[name] = {
            "source": str(source),
            "destination": str(destination),
            "files": inventory["files"],
            "bytes": inventory["bytes"],
        }
    return {"status": "complete", "components": components}


TRAINING_REQUIRED_FIELDS = (
    "model",
    "data_root",
    "manifest",
    "project",
    "name",
    "epochs",
    "patience",
    "batch",
    "imgsz",
    "workers",
    "seed",
    "deterministic",
    "cos_lr",
    "device",
)


def load_training_config(path: Path, project_root: Path) -> Dict[str, object]:
    """Load a portable training config and bind its paths to one project root."""

    root = Path(project_root).expanduser().resolve()
    config_path = Path(path).expanduser().resolve()
    try:
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ValueError("cannot read training config: {}".format(config_path)) from exc
    if not isinstance(payload, dict):
        raise ValueError("training config must be a mapping")
    missing = [field for field in TRAINING_REQUIRED_FIELDS if field not in payload]
    if missing:
        raise ValueError("training config missing fields: {}".format(", ".join(missing)))

    config = dict(payload)
    for field in ("model", "data_root", "manifest", "project"):
        value = Path(str(payload[field]))
        resolved = (root / value).resolve() if not value.is_absolute() else value.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ValueError("{} is outside project root".format(field)) from exc
        config[field] = resolved

    for field in ("epochs", "patience", "batch", "imgsz"):
        value = payload[field]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError("{} must be a positive integer".format(field))
    for field in ("workers", "seed"):
        value = payload[field]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("{} must be a non-negative integer".format(field))
    for field in ("deterministic", "cos_lr"):
        if not isinstance(payload[field], bool):
            raise ValueError("{} must be boolean".format(field))
    if not str(payload["name"]).strip():
        raise ValueError("name must not be empty")
    config["project_root"] = root
    return config


def write_runtime_data_yaml(dataset_root: Path, destination: Path) -> Path:
    """Write the canonical Ultralytics data file for a dataset in this checkout.

    Every path is bound to the resolved ``dataset_root`` on this machine, so the
    file stays valid after the dataset is rebuilt or imported from another host.
    Rebuilds, imports, and training all publish this same content.
    """
    dataset = Path(dataset_root).expanduser().resolve()
    target = Path(destination).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "path": str(dataset),
        "train": "images/train",
        "val": "images/valid",
        "test": "images/test",
        "names": dict(CLASS_NAMES),
    }
    target.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return target


def build_train_kwargs(
    config: Mapping[str, object], smoke: bool, device: Optional[str]
) -> Dict[str, object]:
    selected_device = str(device) if device is not None else str(config["device"])
    kwargs = {
        "project": str(config["project"]),
        "name": str(config["name"]),
        "epochs": int(config["epochs"]),
        "patience": int(config["patience"]),
        "batch": int(config["batch"]),
        "imgsz": int(config["imgsz"]),
        "workers": int(config["workers"]),
        "seed": int(config["seed"]),
        "deterministic": bool(config["deterministic"]),
        "cos_lr": bool(config["cos_lr"]),
        "device": selected_device,
        "pretrained": True,
        "val": True,
        "plots": True,
        "exist_ok": False,
    }
    if smoke:
        kwargs.update({"name": "smoke_e1", "epochs": 1, "fraction": 0.02})
    return kwargs


def check_training_runtime(config: Mapping[str, object]) -> Dict[str, object]:
    """Inspect dependencies and verify every manifest sample is materialized."""

    model = Path(config["model"])
    dataset = Path(config["data_root"])
    manifest = Path(config["manifest"])
    if not model.is_file():
        raise FileNotFoundError("pretrained model not found: {}".format(model))
    if not dataset.is_dir():
        raise FileNotFoundError("training dataset not found: {}".format(dataset))
    rows = load_manifest(manifest)
    for row in rows:
        image = _safe_child(dataset, Path(row.output_image.as_posix()))
        label = _safe_child(dataset, Path(row.output_label.as_posix()))
        if not image.is_file() or not label.is_file():
            raise ManifestError("training dataset is missing a manifest sample")
        class_id, instances = parse_label(label.read_bytes())
        if class_id != row.class_id or instances != row.instances:
            raise ManifestError("training label differs from manifest metadata")

    try:
        import torch
        import ultralytics
    except ImportError as exc:
        raise RuntimeError("PyTorch and Ultralytics are required for training") from exc
    requested = str(config["device"])
    selected = "0" if requested == "auto" and torch.cuda.is_available() else requested
    if requested == "auto" and not torch.cuda.is_available():
        selected = "cpu"
    return {
        "status": "ready",
        "torch": str(torch.__version__),
        "ultralytics": str(ultralytics.__version__),
        "cuda_available": bool(torch.cuda.is_available()),
        "selected_device": selected,
        "splits": split_counts(rows),
        "model_sha256": sha256_file(model),
        "model": str(model),
        "dataset": str(dataset),
        "output": str(config["project"]),
    }


def unicode_safe_save(save, obj, destination, *args, **kwargs):
    """Serialize with ``save`` without handing PyTorch a non-ASCII file path.

    PyTorch's checkpoint writer resolves the destination's parent directory
    through the Windows ANSI code page, so ``torch.save`` fails with
    "Parent directory ... does not exist" whenever this project lives under a
    non-ASCII path such as ``F:\\new大创``. Ultralytics already avoids that for
    its own checkpoints by serializing into an in-memory buffer and calling
    ``Path.write_bytes``; this helper applies the same technique to any writer
    that accepts a destination path or file-like object.
    """

    is_path = isinstance(destination, (str, os.PathLike))
    if not is_path or str(destination).isascii():
        return save(obj, destination, *args, **kwargs)

    buffer = io.BytesIO()
    result = save(obj, buffer, *args, **kwargs)
    Path(destination).write_bytes(buffer.getvalue())
    return result


@contextmanager
def unicode_safe_torch_save():
    """Route ``torch.save`` through a buffer while the block is active.

    Install this after importing Ultralytics, because Ultralytics replaces
    ``torch.save`` with its own retrying wrapper at import time.
    """

    import torch

    original = torch.save

    def save(obj, destination, *args, **kwargs):
        return unicode_safe_save(original, obj, destination, *args, **kwargs)

    torch.save = save
    try:
        yield
    finally:
        torch.save = original


def recorded_output_root(checkpoint: Path) -> Optional[Path]:
    """Read the output root recorded inside an Ultralytics checkpoint."""

    import torch

    payload = torch.load(str(checkpoint), map_location="cpu")
    recorded = payload.get("train_args") or payload.get("args") or {}
    project = recorded.get("project")
    if project is None:
        return None
    return Path(str(project)).expanduser()


def require_portable_resume(checkpoint: Path, project_root: Path) -> None:
    """Fail closed when a checkpoint would write outside the portable output root.

    Ultralytics replaces every training argument with the checkpoint's own on
    resume (``BaseTrainer.check_resume``), so the destination comes from the
    checkpoint rather than from ``--project-root``. This project's archived run
    records an ``E:`` drive root, so resuming it would quietly train there
    instead of inside the portable output directory.
    """

    recorded = recorded_output_root(checkpoint)
    if recorded is None:
        raise ValueError(
            "resume checkpoint records no output root: {}".format(checkpoint)
        )
    try:
        recorded.resolve().relative_to(Path(project_root).expanduser().resolve())
    except ValueError as exc:
        raise ValueError(
            "resume checkpoint output root is outside the portable project: {}".format(
                recorded
            )
        ) from exc


def run_training(
    config: Mapping[str, object],
    smoke: bool,
    device: Optional[str],
    resume: Optional[Path],
):
    """Run Ultralytics training using validated portable paths."""

    resume_path = None
    if resume is not None:
        resume_path = Path(resume).expanduser().resolve()
        if not resume_path.is_file():
            raise FileNotFoundError("resume checkpoint not found: {}".format(resume_path))
        require_portable_resume(resume_path, Path(config["project"]))
    elif not Path(config["model"]).is_file():
        raise FileNotFoundError("pretrained model not found: {}".format(config["model"]))

    runtime = check_training_runtime(config)
    selected_device = str(device) if device is not None else str(runtime["selected_device"])
    output_project = Path(config["project"])
    runtime_yaml = write_runtime_data_yaml(
        Path(config["data_root"]), output_project / "waid4500_runtime_data.yaml"
    )
    kwargs = build_train_kwargs(config, smoke=smoke, device=selected_device)
    kwargs["data"] = str(runtime_yaml)
    model_path = resume_path if resume_path is not None else Path(config["model"])
    if resume_path is not None:
        kwargs["resume"] = str(resume_path)

    from ultralytics import YOLO

    with unicode_safe_torch_save():
        return YOLO(str(model_path)).train(**kwargs)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _checksum_relative_path(value: str) -> PurePosixPath:
    if not value or "\\" in value or ":" in value:
        raise ValueError("checksum path is not canonical")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value:
        raise ValueError("checksum path must be relative POSIX")
    if any(part in ("", ".", "..") for part in path.parts):
        raise ValueError("checksum path escapes project root")
    return path


def load_checksums(path: Path) -> Dict[str, str]:
    checksums = {}
    try:
        lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ValueError("cannot read checksums: {}".format(path)) from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        parts = line.split("  ", 1)
        if len(parts) != 2 or not SHA256_PATTERN.fullmatch(parts[0]):
            raise ValueError("invalid checksum line {}".format(line_number))
        relative = _checksum_relative_path(parts[1]).as_posix()
        if relative in checksums:
            raise ValueError("duplicate checksum path: {}".format(relative))
        checksums[relative] = parts[0]
    if not checksums:
        raise ValueError("checksum file must not be empty")
    return checksums


def write_checksums(project_root: Path, paths: Iterable[Path], destination: Path) -> Path:
    root = Path(project_root).expanduser().resolve()
    entries = []
    for path in paths:
        artifact = Path(path).expanduser().resolve()
        try:
            relative = artifact.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError("checksum artifact is outside project root") from exc
        if not artifact.is_file():
            raise FileNotFoundError("checksum artifact not found: {}".format(artifact))
        entries.append((relative, sha256_file(artifact)))
    if not entries:
        raise ValueError("at least one checksum artifact is required")
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "".join("{}  {}\n".format(digest, relative) for relative, digest in sorted(entries)),
        encoding="utf-8",
    )
    return target


def verify_checksums(project_root: Path, checksums_path: Path) -> List[Dict[str, object]]:
    root = Path(project_root).expanduser().resolve()
    results = []
    for relative, expected in load_checksums(checksums_path).items():
        artifact = _safe_child(root, Path(relative))
        actual = sha256_file(artifact) if artifact.is_file() else None
        results.append(
            {
                "path": relative,
                "expected": expected,
                "actual": actual,
                "status": "passed" if actual == expected else "failed",
            }
        )
    return results


def summarize_results(results_csv: Path) -> Dict[str, object]:
    required = (
        "epoch",
        "metrics/precision(B)",
        "metrics/recall(B)",
        "metrics/mAP50(B)",
        "metrics/mAP50-95(B)",
    )
    try:
        with Path(results_csv).open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not set(required).issubset(set(reader.fieldnames or ())):
                raise ValueError("results.csv is missing required metric columns")
            rows = list(reader)
    except OSError as exc:
        raise ValueError("cannot read results.csv") from exc
    if not rows:
        raise ValueError("results.csv must contain at least one epoch")
    try:
        best = max(rows, key=lambda row: float(row["metrics/mAP50-95(B)"]))
        return {
            "epochs_recorded": len(rows),
            "selection_metric": "metrics/mAP50-95(B)",
            "best": {
                "epoch": int(float(best["epoch"])),
                "precision": float(best["metrics/precision(B)"]),
                "recall": float(best["metrics/recall(B)"]),
                "map50": float(best["metrics/mAP50(B)"]),
                "map50_95": float(best["metrics/mAP50-95(B)"]),
            },
        }
    except (TypeError, ValueError) as exc:
        raise ValueError("results.csv contains invalid numeric metrics") from exc


def capture_environment() -> Dict[str, object]:
    try:
        import torch

        torch_version = str(torch.__version__)
        cuda_available = bool(torch.cuda.is_available())
        cuda_version = str(torch.version.cuda) if torch.version.cuda is not None else None
        gpu = torch.cuda.get_device_name(0) if cuda_available else None
    except ImportError:
        torch_version = None
        cuda_available = False
        cuda_version = None
        gpu = None
    try:
        import ultralytics

        ultralytics_version = str(ultralytics.__version__)
    except ImportError:
        ultralytics_version = None
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "torch": torch_version,
        "ultralytics": ultralytics_version,
        "cuda_available": cuda_available,
        "cuda": cuda_version,
        "gpu": gpu,
    }


def verify_reproduction(
    project_root: Path, manifest_path: Path, checksums_path: Path
) -> Dict[str, object]:
    root = Path(project_root).expanduser().resolve()
    report = {}

    try:
        rows = load_manifest(manifest_path)
        checksum_results = verify_checksums(root, checksums_path)
        asset_status = (
            "passed" if all(item["status"] == "passed" for item in checksum_results) else "failed"
        )
        report["assets"] = {
            "status": asset_status,
            "splits": split_counts(rows),
            "checksums": checksum_results,
        }
    except Exception as exc:
        report["assets"] = {"status": "failed", "error": str(exc)}

    try:
        archived = root / "outputs/training/waid4500_yolo11s/run/weights/best.pt"
        delivery = root / "models/detection/yolo11s-waid.pt"
        archived_hash = sha256_file(archived)
        delivery_hash = sha256_file(delivery)
        lineage_status = (
            "passed"
            if archived_hash == delivery_hash == PRODUCTION_MODEL_SHA256
            else "failed"
        )
        report["lineage"] = {
            "status": lineage_status,
            "expected": PRODUCTION_MODEL_SHA256,
            "archived_best": archived_hash,
            "delivery_model": delivery_hash,
        }
    except Exception as exc:
        report["lineage"] = {"status": "failed", "error": str(exc)}

    environment = capture_environment()
    runtime_status = (
        "passed"
        if environment["torch"] is not None and environment["ultralytics"] is not None
        else "failed"
    )
    report["runtime"] = {"status": runtime_status, **environment}

    try:
        summary = summarize_results(
            root / "outputs/training/waid4500_yolo11s/run/results.csv"
        )
        report["results"] = {"status": "passed", **summary}
    except Exception as exc:
        report["results"] = {"status": "failed", "error": str(exc)}

    report["status"] = (
        "passed"
        if all(report[section]["status"] == "passed" for section in ("assets", "lineage", "runtime", "results"))
        else "failed"
    )
    return report

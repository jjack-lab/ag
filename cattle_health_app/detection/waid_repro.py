"""Portable WAID4500 dataset and training reproducibility helpers."""

from __future__ import annotations

import csv
import filecmp
import json
import shutil
import tempfile
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

        data_yaml = {
            "path": str(output),
            "train": "images/train",
            "val": "images/valid",
            "test": "images/test",
            "names": dict(CLASS_NAMES),
        }
        (staging / "data.yaml").write_text(
            yaml.safe_dump(data_yaml, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
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

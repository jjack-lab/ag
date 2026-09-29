"""Portable WAID4500 dataset and training reproducibility helpers."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Dict, Iterable, List, Tuple


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

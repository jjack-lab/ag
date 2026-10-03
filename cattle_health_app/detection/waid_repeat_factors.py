"""LVIS-style repeat-factor sampling for the WAID4500 training split.

Ultralytics detection training has no class-balanced sampler, and the frozen
WAID4500 training split is imbalanced (zebra 289 images against 1041 for sheep).
The H1 improvement hypothesis rebalances the *training list* instead: every
image receives the largest repeat factor of the classes it contains, and those
weights are materialised deterministically with largest-remainder
apportionment. The dataset, the labels and the frozen split are not modified.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Tuple

IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".bmp", ".webp")


def _label_files(dataset_root: Path, split: str) -> List[Path]:
    labels = Path(dataset_root).expanduser().resolve() / "labels" / split
    if not labels.is_dir():
        raise FileNotFoundError("label split not found: {}".format(labels))
    return sorted(
        path
        for path in labels.iterdir()
        if path.is_file() and path.suffix.lower() == ".txt"
    )


def _classes_in_label(content: str) -> Tuple[int, ...]:
    classes = []
    for number, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split()
        if len(parts) != 5:
            raise ValueError("label line {} must have 5 fields".format(number))
        try:
            class_id = int(parts[0])
        except ValueError as exc:
            raise ValueError("label line {} has a non-integer class".format(number)) from exc
        if class_id < 0:
            raise ValueError("label line {} has a negative class".format(number))
        classes.append(class_id)
    if not classes:
        raise ValueError("label file has no objects")
    return tuple(classes)


def class_image_counts(dataset_root: Path, split: str) -> Dict[int, int]:
    """Count the images of a split that contain each class at least once."""

    counts: Dict[int, int] = {}
    for path in _label_files(dataset_root, split):
        for class_id in set(_classes_in_label(path.read_text(encoding="utf-8"))):
            counts[class_id] = counts.get(class_id, 0) + 1
    if not counts:
        raise ValueError("no labelled classes found in split {}".format(split))
    return dict(sorted(counts.items()))


def repeat_factors(counts: Mapping[int, int]) -> Dict[int, float]:
    """Return ``max(1, sqrt(head_count / class_count))`` for every class."""

    if not counts:
        raise ValueError("counts must not be empty")
    values: Dict[int, int] = {}
    for class_id, count in counts.items():
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise ValueError("class counts must be positive integers")
        values[int(class_id)] = count
    head = max(values.values())
    return {
        class_id: max(1.0, math.sqrt(head / count))
        for class_id, count in values.items()
    }


def apportion_copies(weights: Sequence[float], total: int) -> List[int]:
    """Turn fractional weights into integer copies with largest remainders."""

    values = [float(weight) for weight in weights]
    if any(weight < 1.0 for weight in values):
        raise ValueError("every image weight must be at least 1")
    if isinstance(total, bool) or not isinstance(total, int) or total < len(values):
        raise ValueError("total must be an integer >= the number of images")
    copies = [int(math.floor(weight)) for weight in values]
    remaining = total - sum(copies)
    remainders = [weight - math.floor(weight) for weight in values]
    while remaining > 0:
        order = sorted(range(len(values)), key=lambda i: (-remainders[i], i))
        for index in order:
            if remaining == 0:
                break
            copies[index] += 1
            remaining -= 1
    while remaining < 0:
        order = sorted(range(len(values)), key=lambda i: (remainders[i], -i))
        for index in order:
            if remaining == 0:
                break
            if copies[index] > 1:
                copies[index] -= 1
                remaining += 1
    return copies


def _image_for_label(dataset_root: Path, split: str, label: Path) -> Path:
    images = dataset_root / "images" / split
    matches = sorted(
        path
        for path in images.glob("{}.*".format(label.stem))
        if path.suffix.lower() in IMAGE_SUFFIXES
    )
    if not matches:
        raise FileNotFoundError("image for label not found: {}".format(label.name))
    return matches[0]


def write_repeat_list(
    dataset_root: Path, split: str, destination: Path
) -> Path:
    """Write a deterministic Ultralytics train list with repeat factors applied."""

    root = Path(dataset_root).expanduser().resolve()
    labels = _label_files(root, split)
    factors = repeat_factors(class_image_counts(root, split))

    entries: List[Tuple[Path, float]] = []
    for label in labels:
        classes = set(_classes_in_label(label.read_text(encoding="utf-8")))
        weight = max(factors[class_id] for class_id in classes)
        entries.append((_image_for_label(root, split, label), weight))
    entries.sort(key=lambda item: item[0].as_posix())

    weights = [weight for _, weight in entries]
    total = max(len(entries), int(round(sum(weights))))
    copies = apportion_copies(weights, total)

    lines: List[str] = []
    for (image, _weight), count in zip(entries, copies):
        relative = image.relative_to(root).as_posix()
        lines.extend([relative] * count)
    target = Path(destination).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("".join("{}\n".format(line) for line in lines), encoding="utf-8")
    return target

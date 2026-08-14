"""Build leakage-safe CVB manifests from AVA annotation CSV files.

Manifest ``frame_paths`` values are JSON arrays of paths relative to data_root.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import shutil
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType
from typing import Dict, Iterable, Iterator, Mapping, Sequence, Tuple

import cv2

from cattle_health_app.behavior.cvb_labels import CVB_LABELS


FRAME_COUNT = 16
DURATION_SECONDS = 2.0
DEFAULT_FPS = 30.0


@dataclass(frozen=True)
class AvaAnnotation:
    video_id: str
    timestamp_seconds: float
    bbox: tuple[float, float, float, float]
    label_id: int
    track_id: int


@dataclass(frozen=True)
class IndexedClip:
    sample_id: str
    video_id: str
    timestamp_seconds: float
    bbox: tuple[float, float, float, float]
    label_id: int
    track_id: int
    group_id: str
    frame_paths: tuple[str, ...]
    split: str


@dataclass(frozen=True)
class IndexResult:
    accepted_count: int
    rejected_count: int
    rejected_by_reason: dict[str, int]
    split_counts: dict[str, int]
    output: Path


def parse_ava_row(row: Sequence[str]) -> AvaAnnotation:
    if len(row) != 8:
        raise ValueError("AVA row must contain exactly 8 columns")
    video_id = row[0]
    if not video_id:
        raise ValueError("video_id must not be empty")
    basename = video_id.split(".", 1)[0].upper()
    if (not _SAFE_VIDEO_ID.fullmatch(video_id) or video_id.endswith((".", " "))
            or basename in _RESERVED_WINDOWS_NAMES):
        raise ValueError("video_id is not a safe Windows filename")
    try:
        timestamp = float(row[1])
        bbox = tuple(float(value) for value in row[2:6])
        label_id = int(row[6])
        track_id = int(row[7])
    except (TypeError, ValueError) as exc:
        raise ValueError("AVA row contains an invalid numeric value") from exc
    if not math.isfinite(timestamp) or timestamp <= 0:
        raise ValueError("timestamp_seconds must be finite and positive")
    if not all(math.isfinite(value) for value in bbox):
        raise ValueError("bbox coordinates must be finite")
    x1, y1, x2, y2 = bbox
    if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
        raise ValueError("bbox must be normalized and non-empty")
    if label_id not in CVB_LABELS:
        raise ValueError("unknown label_id")
    if track_id < 0:
        raise ValueError("track_id must be nonnegative")
    return AvaAnnotation(video_id, timestamp, bbox, label_id, track_id)


_SAFE_VIDEO_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+\-]*$")
_RESERVED_WINDOWS_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


_GROUP_PATTERN = re.compile(
    r"(?:^|_)"
    r"(?P<group>arm[^_]+_gopro[^_]+_\d{8}_\d{6})"
    r"(?:_|$)"
)


def group_id_for_video(video_id: str) -> str:
    normalized = re.sub(r"\+\d+$", "", video_id)
    match = _GROUP_PATTERN.search(normalized)
    return match.group("group") if match else normalized


def select_frame_numbers(
    timestamp_seconds: float,
    available_numbers: Iterable[int],
    fps: float = DEFAULT_FPS,
    frame_count: int = FRAME_COUNT,
    duration_seconds: float = DURATION_SECONDS,
) -> list[int]:
    available = sorted(set(available_numbers))
    if (not math.isfinite(fps) or fps <= 0 or frame_count < 2
            or not math.isfinite(duration_seconds) or duration_seconds <= 0):
        raise ValueError("fps, frame_count, and duration_seconds must be positive")
    if len(available) < frame_count:
        raise ValueError("insufficient_frames")
    first, last = available[0], available[-1]
    span = max(frame_count, int(round(fps * duration_seconds)))
    start = int(round(timestamp_seconds * fps - span / 2)) + 1
    start = max(first, min(start, last - span + 1))
    end = min(last, start + span - 1)
    if end - start + 1 < frame_count:
        start = max(first, end - frame_count + 1)
    numbers = [round(start + index * (end - start) / (frame_count - 1)) for index in range(frame_count)]
    if len(set(numbers)) != frame_count:
        raise ValueError("insufficient_frames")
    return numbers


def _iter_annotations(path: Path, source_split: str) -> Iterator[Tuple[AvaAnnotation | None, str, int, list[str], str | None]]:
    """Yield each CSV row once; callers aggregate without retaining source lists."""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row_number, row in enumerate(csv.reader(handle), 1):
            if not row:
                continue
            try:
                annotation = parse_ava_row(row)
            except ValueError as exc:
                yield None, source_split, row_number, row, str(exc)
            else:
                yield annotation, source_split, row_number, row, None

def _identity(annotation: AvaAnnotation):
    return (annotation.video_id, annotation.timestamp_seconds, annotation.track_id, annotation.bbox)


def _sample_id(annotation: AvaAnnotation) -> str:
    value = repr((annotation.video_id, annotation.timestamp_seconds, annotation.bbox, annotation.label_id, annotation.track_id))
    return sha256(value.encode("utf-8")).hexdigest()[:20]


def _assign_train_val(groups: Iterable[str], seed: int) -> dict[str, str]:
    ordered = sorted(set(groups), key=lambda group: sha256(f"{seed}:{group}".encode()).hexdigest())
    if len(ordered) < 2:
        return {group: "train" for group in ordered}
    val_count = max(1, int(round(len(ordered) * 0.2)))
    val_groups = set(ordered[-val_count:])
    return {group: ("val" if group in val_groups else "train") for group in ordered}


def _write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build_index(
    data_root: str | Path,
    train_ava: str | Path,
    test_ava: str | Path,
    output: str | Path,
    seed: int = 20260814,
    overwrite: bool = False,
    fps: float = DEFAULT_FPS,
) -> IndexResult:
    data_root, train_ava, test_ava, output = map(Path, (data_root, train_ava, test_ava, output))
    data_root = data_root.resolve()
    frames_root = (data_root / "raw_frames").resolve()
    if output.exists() and not overwrite:
        raise FileExistsError(f"Output already exists: {output}")
    rejected = []
    # One compact representative and count per identity/label; each CSV is consumed once.
    aggregates = defaultdict(dict)
    for source_path, source_split in ((train_ava, "train"), (test_ava, "test")):
        for annotation, source, row_number, row, error in _iter_annotations(source_path, source_split):
            if annotation is None:
                rejected.append((source, row_number, "invalid_annotation", row, error))
                continue
            labels = aggregates[_identity(annotation)]
            record = labels.get(annotation.label_id)
            if record is None:
                labels[annotation.label_id] = [annotation, source, row_number, row, 1]
            else:
                record[4] += 1
                if source == "test":
                    record[1:4] = [source, row_number, row]

    candidates = []
    for labels in aggregates.values():
        records = list(labels.values())
        if len(records) > 1:
            for annotation, source, row_number, row, count in records:
                rejected.extend((source, row_number, "conflicting_labels", row, "same target has multiple labels") for _ in range(count))
        else:
            candidates.append(tuple(records[0][:4]))
    del aggregates

    test_groups = {group_id_for_video(item[0].video_id) for item in candidates if item[1] == "test"}
    train_groups = [group_id_for_video(item[0].video_id) for item in candidates if item[1] == "train" and group_id_for_video(item[0].video_id) not in test_groups]
    assigned = _assign_train_val(train_groups, seed)
    validation_cache: dict[Path, str | None] = {}
    video_cache: Dict[str, Tuple[Path | None, Mapping[int, Path], str | None]] = {}
    clips = []
    for annotation, source, row_number, row in sorted(candidates, key=lambda item: (item[1], item[0].video_id, item[0].timestamp_seconds, item[0].track_id, item[0].bbox, item[0].label_id)):
        inventory = video_cache.get(annotation.video_id)
        if inventory is None:
            frame_dir = (frames_root / annotation.video_id).resolve()
            if frame_dir.parent != frames_root:
                inventory = (None, {}, "invalid_video_path")
            else:
                discovered = {}
                if frame_dir.is_dir():
                    for path in frame_dir.glob("img_*.jpg"):
                        match = re.fullmatch(r"img_(\d{5})\.jpg", path.name)
                        if match:
                            discovered[int(match.group(1))] = path
                inventory = (frame_dir, MappingProxyType(discovered), None)
            video_cache[annotation.video_id] = inventory
        frame_dir, frame_map, inventory_error = inventory
        if inventory_error:
            rejected.append((source, row_number, inventory_error, row, inventory_error))
            continue
        try:
            if not frame_map:
                raise ValueError("missing_frame")
            numbers = select_frame_numbers(annotation.timestamp_seconds, frame_map.keys(), fps=fps)
        except ValueError as exc:
            reason = str(exc) if str(exc) in {"missing_frame", "insufficient_frames"} else "insufficient_frames"
            rejected.append((source, row_number, reason, row, reason))
            continue
        original_paths = [frame_map.get(number, frame_dir / f"img_{number:05d}.jpg") for number in numbers]
        safe_paths = []
        bad_reason = None
        for original in original_paths:
            resolved = original.resolve()
            if resolved.parent != frame_dir or frame_dir.parent != frames_root:
                bad_reason = "frame_path_escape"
                break
            if resolved not in validation_cache:
                if not resolved.is_file():
                    validation_cache[resolved] = "missing_frame"
                elif resolved.with_name(resolved.name + ".aria2").exists():
                    validation_cache[resolved] = "partial_frame"
                elif cv2.imread(str(resolved), cv2.IMREAD_COLOR) is None:
                    validation_cache[resolved] = "undecodable_frame"
                else:
                    validation_cache[resolved] = None
            if validation_cache[resolved]:
                bad_reason = validation_cache[resolved]
                break
            safe_paths.append(resolved)
        if bad_reason:
            rejected.append((source, row_number, bad_reason, row, bad_reason))
            continue
        paths = safe_paths
        group_id = group_id_for_video(annotation.video_id)
        split = "test" if group_id in test_groups else assigned[group_id]
        relative_paths = [path.resolve().relative_to(data_root).as_posix() for path in paths]
        if any(".." in Path(path).parts for path in relative_paths):
            raise ValueError("manifest frame path escapes data_root")
        relative = tuple(relative_paths)
        clips.append(IndexedClip(_sample_id(annotation), annotation.video_id, annotation.timestamp_seconds, annotation.bbox, annotation.label_id, annotation.track_id, group_id, relative, split))

    groups_by_split = {split: {clip.group_id for clip in clips if clip.split == split} for split in ("train", "val", "test")}
    leakage = any(groups_by_split[left] & groups_by_split[right] for left, right in (("train", "val"), ("train", "test"), ("val", "test")))
    if leakage:
        raise ValueError("group leakage between official test and training data")

    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent))
    try:
        fields = ["sample_id", "video_id", "timestamp_seconds", "x1", "y1", "x2", "y2", "label_id", "track_id", "group_id", "frame_paths"]
        split_counts = {}
        for split in ("train", "val", "test"):
            selected = sorted((clip for clip in clips if clip.split == split), key=lambda clip: clip.sample_id)
            split_counts[split] = len(selected)
            rows = [{
                "sample_id": clip.sample_id, "video_id": clip.video_id, "timestamp_seconds": f"{clip.timestamp_seconds:g}",
                "x1": f"{clip.bbox[0]:g}", "y1": f"{clip.bbox[1]:g}", "x2": f"{clip.bbox[2]:g}", "y2": f"{clip.bbox[3]:g}",
                "label_id": clip.label_id, "track_id": clip.track_id, "group_id": clip.group_id,
                "frame_paths": json.dumps(clip.frame_paths, ensure_ascii=False, separators=(",", ":")),
            } for clip in selected]
            _write_csv(staging / f"{split}.csv", fields, rows)
        rejected_sorted = sorted(rejected, key=lambda item: (item[0], item[1], item[2], item[3]))
        _write_csv(staging / "rejected.csv", ["source_split", "row_number", "reason", "row", "detail"], ({"source_split": source, "row_number": number, "reason": reason, "row": json.dumps(row, ensure_ascii=False), "detail": detail} for source, number, reason, row, detail in rejected_sorted))
        reasons = dict(sorted(Counter(item[2] for item in rejected).items()))
        class_counts = Counter(clip.label_id for clip in clips)
        report = {
            "accepted_count": len(clips), "rejected_count": len(rejected), "rejected_by_reason": reasons,
            "per_split_counts": split_counts, "per_class_counts": {str(label): class_counts[label] for label in range(1, 13)},
            "source_paths": {"data_root": str(data_root), "train_ava": str(train_ava), "test_ava": str(test_ava)},
            "seed": seed, "frame_count": FRAME_COUNT, "fps": fps, "duration_seconds": DURATION_SECONDS,
            "group_leakage": False,
        }
        (staging / "quality_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        backup = None
        if output.exists():
            backup = Path(tempfile.mkdtemp(prefix=f".{output.name}.backup-", dir=output.parent))
            backup.rmdir()
            os.replace(output, backup)
        try:
            os.replace(staging, output)
        except BaseException:
            if backup is not None:
                os.replace(backup, output)
            raise
        if backup is not None:
            shutil.rmtree(backup)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return IndexResult(len(clips), len(rejected), dict(sorted(Counter(item[2] for item in rejected).items())), split_counts, output)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--train-ava", required=True, type=Path)
    parser.add_argument("--test-ava", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=20260814)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    build_index(args.data_root, args.train_ava, args.test_ava, args.output, args.seed, args.overwrite)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


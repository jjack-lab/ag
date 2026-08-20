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
import sqlite3
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


def _ensure_training_class_coverage(connection: sqlite3.Connection, seed: int) -> list[dict]:
    """Move the deterministic minimum number of whole groups needed by train."""
    train_labels = {row[0] for row in connection.execute(
        "SELECT DISTINCT label_id FROM accepted WHERE split='train'"
    )}
    all_labels={row[0] for row in connection.execute("SELECT DISTINCT label_id FROM accepted")}
    if all_labels != set(range(1,13)): return []

    missing = set(range(1, 13)) - train_labels
    if not missing:
        return []
    candidates = []
    for group_id, split, row_count in connection.execute(
        "SELECT group_id,split,COUNT(*) FROM accepted WHERE split!='train' GROUP BY group_id,split"
    ):
        labels = {row[0] for row in connection.execute(
            "SELECT DISTINCT label_id FROM accepted WHERE group_id=?", (group_id,)
        )}
        covered = labels & missing
        if covered:
            mask = sum(1 << (label - 1) for label in covered)
            candidates.append((group_id, split, row_count, labels, mask))
    candidates.sort(key=lambda item: sha256(f"{seed}:{item[0]}".encode()).hexdigest())
    target=0
    for candidate in candidates: target|=candidate[4]
    if not target: return []

    states = {0: ((0, 0, 0, ()), ())}
    for group_id, split, row_count, labels, mask in candidates:
        snapshot = list(states.items())
        for existing_mask, (cost, selected) in snapshot:
            combined = existing_mask | mask
            group_ids = tuple(sorted((*cost[3], group_id)))
            candidate_cost = (cost[0] + 1, cost[1] + (split == "test"), cost[2] + row_count, group_ids)
            current = states.get(combined)
            if current is None or candidate_cost < current[0]:
                states[combined] = (candidate_cost, (*selected, (group_id, split, row_count, labels)))
    if target not in states:
        raise RuntimeError("failed to compute deterministic training class coverage")
    moves = []
    for group_id, split, row_count, labels in states[target][1]:
        connection.execute("UPDATE accepted SET split='train' WHERE group_id=?", (group_id,))
        moves.append({"group_id": group_id, "from_split": split, "to_split": "train",
                      "labels": sorted(labels), "row_count": row_count})
    connection.commit()
    return sorted(moves, key=lambda move: move["group_id"])

def _write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _candidate_query() -> str:
    return """
        WITH ranked AS (
          SELECT *, ROW_NUMBER() OVER (
            PARTITION BY identity ORDER BY CASE source WHEN 'test' THEN 0 ELSE 1 END, row_number
          ) AS rank
          FROM occurrences
          WHERE identity IN (
            SELECT identity FROM occurrences GROUP BY identity HAVING COUNT(DISTINCT label_id) = 1
          )
        ) SELECT * FROM ranked WHERE rank = 1
        ORDER BY source, video_id, timestamp, track_id, x1, y1, x2, y2, label_id
    """


def _annotation_from_record(record: sqlite3.Row) -> AvaAnnotation:
    return AvaAnnotation(record["video_id"], record["timestamp"],
                         (record["x1"], record["y1"], record["x2"], record["y2"]),
                         record["label_id"], record["track_id"])


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
    logical_frames_root = data_root / "raw_frames"
    frames_root = logical_frames_root.resolve()
    if frames_root != logical_frames_root or frames_root.parent != data_root:
        raise ValueError("raw_frames root must not be a symlink, junction, or external reparse target")
    if output.exists() and not overwrite:
        raise FileExistsError(f"Output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent))
    database = staging / "index-spool.sqlite3"
    connection = sqlite3.connect(str(database))
    connection.row_factory = sqlite3.Row
    try:
        connection.executescript("""
          CREATE TABLE occurrences(identity TEXT, video_id TEXT, timestamp REAL, x1 REAL, y1 REAL,
            x2 REAL, y2 REAL, label_id INTEGER, track_id INTEGER, source TEXT, row_number INTEGER, raw_json TEXT);
          CREATE INDEX occurrence_identity ON occurrences(identity);
          CREATE TABLE rejected(source TEXT, row_number INTEGER, reason TEXT, raw_json TEXT, detail TEXT);
          CREATE TABLE accepted(sample_id TEXT, video_id TEXT, timestamp REAL, x1 REAL, y1 REAL, x2 REAL, y2 REAL,
            label_id INTEGER, track_id INTEGER, group_id TEXT, frame_paths TEXT, split TEXT);
        """)
        for source_path, source_split in ((train_ava, "train"), (test_ava, "test")):
            for annotation, source, row_number, row, error in _iter_annotations(source_path, source_split):
                raw_json = json.dumps(row, ensure_ascii=False)
                if annotation is None:
                    connection.execute("INSERT INTO rejected VALUES (?,?,?,?,?)",
                                       (source, row_number, "invalid_annotation", raw_json, error))
                    continue
                identity = repr(_identity(annotation))
                connection.execute("INSERT INTO occurrences VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
                    identity, annotation.video_id, annotation.timestamp_seconds, *annotation.bbox,
                    annotation.label_id, annotation.track_id, source, row_number, raw_json))
        connection.execute("""INSERT INTO rejected
          SELECT source,row_number,'conflicting_labels',raw_json,'same target has multiple labels'
          FROM occurrences WHERE identity IN (
            SELECT identity FROM occurrences GROUP BY identity HAVING COUNT(DISTINCT label_id)>1)""")
        connection.commit()

        test_groups = set()
        train_groups = set()
        for row in connection.execute(_candidate_query()):
            group = group_id_for_video(row["video_id"])
            (test_groups if row["source"] == "test" else train_groups).add(group)
        assigned = _assign_train_val(train_groups - test_groups, seed)
        validation_cache: Dict[Path, str | None] = {}
        video_cache: Dict[str, Tuple[Path | None, Mapping[int, Path], str | None]] = {}
        for record in connection.execute(_candidate_query()):
            annotation = _annotation_from_record(record)
            source, row_number, raw_json = record["source"], record["row_number"], record["raw_json"]
            inventory = video_cache.get(annotation.video_id)
            if inventory is None:
                frame_dir = (frames_root / annotation.video_id).resolve()
                if frame_dir.parent != frames_root:
                    inventory = (None, MappingProxyType({}), "invalid_video_path")
                else:
                    discovered = {}
                    if frame_dir.is_dir():
                        for path in frame_dir.glob("img_*.jpg"):
                            match = re.fullmatch(r"img_(\d{5})\.jpg", path.name)
                            if match:
                                discovered[int(match.group(1))] = path
                    inventory = (frame_dir, MappingProxyType(discovered), None)
                video_cache[annotation.video_id] = inventory
            frame_dir, frame_map, error = inventory
            if error:
                connection.execute("INSERT INTO rejected VALUES (?,?,?,?,?)", (source,row_number,error,raw_json,error))
                continue
            try:
                if not frame_map:
                    raise ValueError("missing_frame")
                numbers = select_frame_numbers(annotation.timestamp_seconds, frame_map.keys(), fps=fps)
            except ValueError as exc:
                reason = str(exc) if str(exc) in {"missing_frame", "insufficient_frames"} else "insufficient_frames"
                connection.execute("INSERT INTO rejected VALUES (?,?,?,?,?)", (source,row_number,reason,raw_json,reason))
                continue
            safe_paths = []
            bad_reason = None
            for number in numbers:
                original = frame_map.get(number, frame_dir / f"img_{number:05d}.jpg")
                resolved = original.resolve()
                if resolved.parent != frame_dir or frame_dir.parent != frames_root:
                    bad_reason = "frame_path_escape"
                    break
                if resolved not in validation_cache:
                    if not resolved.is_file(): validation_cache[resolved] = "missing_frame"
                    elif resolved.with_name(resolved.name + ".aria2").exists(): validation_cache[resolved] = "partial_frame"
                    elif cv2.imread(str(resolved), cv2.IMREAD_COLOR) is None: validation_cache[resolved] = "undecodable_frame"
                    else: validation_cache[resolved] = None
                if validation_cache[resolved]:
                    bad_reason = validation_cache[resolved]
                    break
                safe_paths.append(resolved)
            if bad_reason:
                connection.execute("INSERT INTO rejected VALUES (?,?,?,?,?)", (source,row_number,bad_reason,raw_json,bad_reason))
                continue
            group_id = group_id_for_video(annotation.video_id)
            split = "test" if group_id in test_groups else assigned[group_id]
            relative = tuple(path.relative_to(data_root).as_posix() for path in safe_paths)
            if any(".." in Path(path).parts for path in relative):
                raise ValueError("manifest frame path escapes data_root")
            connection.execute("INSERT INTO accepted VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
                _sample_id(annotation), annotation.video_id, annotation.timestamp_seconds, *annotation.bbox,
                annotation.label_id, annotation.track_id, group_id,
                json.dumps(relative, ensure_ascii=False, separators=(",", ":")), split))
        connection.commit()

        split_adjustments = _ensure_training_class_coverage(connection, seed)
        groups_by_split = {split: {row[0] for row in connection.execute(
            "SELECT DISTINCT group_id FROM accepted WHERE split=?", (split,))} for split in ("train","val","test")}
        if any(groups_by_split[a] & groups_by_split[b] for a,b in (("train","val"),("train","test"),("val","test"))):
            raise ValueError("group leakage")
        fields = ["sample_id","video_id","timestamp_seconds","x1","y1","x2","y2","label_id","track_id","group_id","frame_paths"]
        split_counts = {}
        for split in ("train","val","test"):
            split_counts[split] = connection.execute("SELECT COUNT(*) FROM accepted WHERE split=?",(split,)).fetchone()[0]
            cursor = connection.execute("SELECT sample_id,video_id,timestamp AS timestamp_seconds,x1,y1,x2,y2,label_id,track_id,group_id,frame_paths FROM accepted WHERE split=? ORDER BY sample_id",(split,))
            _write_csv(staging/f"{split}.csv", fields, (dict(row) for row in cursor))
        rejected_count = connection.execute("SELECT COUNT(*) FROM rejected").fetchone()[0]
        reasons = dict(connection.execute("SELECT reason,COUNT(*) FROM rejected GROUP BY reason ORDER BY reason"))
        cursor = connection.execute("SELECT source,row_number,reason,raw_json,detail FROM rejected ORDER BY source,row_number,reason,raw_json")
        _write_csv(staging/"rejected.csv", ["source_split","row_number","reason","row","detail"],
                   ({"source_split":r["source"],"row_number":r["row_number"],"reason":r["reason"],"row":r["raw_json"],"detail":r["detail"]} for r in cursor))
        accepted_count = sum(split_counts.values())
        class_counts = dict(connection.execute("SELECT label_id,COUNT(*) FROM accepted GROUP BY label_id"))
        per_split_class_counts = {}
        per_split_missing_classes = {}
        for split in ("train", "val", "test"):
            counts = dict(connection.execute(
                "SELECT label_id,COUNT(*) FROM accepted WHERE split=? GROUP BY label_id", (split,)
            ))
            per_split_class_counts[split] = {str(i): counts.get(i, 0) for i in range(1, 13)}
            per_split_missing_classes[split] = [i for i in range(1, 13) if not counts.get(i, 0)]
        class_group_counts = {str(i): {split: connection.execute(
            "SELECT COUNT(DISTINCT group_id) FROM accepted WHERE label_id=? AND split=?", (i, split)
        ).fetchone()[0] for split in ("train", "val", "test")} for i in range(1, 13)}
        independent_limitations = {str(i): [split for split in ("val", "test")
            if i in per_split_missing_classes[split]] for i in range(1, 13)}
        independent_limitations = {key: value for key, value in independent_limitations.items() if value}
        report = {"accepted_count":accepted_count,"rejected_count":rejected_count,"rejected_by_reason":reasons,
          "per_split_counts":split_counts,"per_class_counts":{str(i):class_counts.get(i,0) for i in range(1,13)},
          "source_paths":{"data_root":str(data_root),"train_ava":str(train_ava),"test_ava":str(test_ava)},
          "seed":seed,"frame_count":FRAME_COUNT,"fps":fps,"duration_seconds":DURATION_SECONDS,"group_leakage":False,
          "per_split_class_counts":per_split_class_counts,"per_split_missing_classes":per_split_missing_classes,
          "per_class_group_counts":class_group_counts,"classes_without_independent_evaluation":independent_limitations,
          "split_adjustments":split_adjustments,
          "official_test_split_modified":any(move["from_split"]=="test" for move in split_adjustments),
          "split_adjustment_reason":"minimum whole-group moves required for 12-class training coverage" if split_adjustments else None}
        (staging/"quality_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        connection.close()
        database.unlink()
        backup = None
        if output.exists():
            backup = Path(tempfile.mkdtemp(prefix=f".{output.name}.backup-",dir=output.parent)); backup.rmdir(); os.replace(output,backup)
        try: os.replace(staging,output)
        except BaseException:
            if backup is not None: os.replace(backup,output)
            raise
        if backup is not None: shutil.rmtree(backup)
        return IndexResult(accepted_count,rejected_count,reasons,split_counts,output)
    except BaseException:
        connection.close()
        shutil.rmtree(staging,ignore_errors=True)
        raise

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


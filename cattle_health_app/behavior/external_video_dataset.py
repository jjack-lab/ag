"""Decode hash-bound virtual external clips with the frozen CVB transform contract."""

import csv
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
from typing import Mapping, Tuple

import cv2
import numpy as np

from cattle_health_app.behavior.cvb_labels import CVB_NAME_TO_ID
from cattle_health_app.behavior.dataset import expand_normalized_box
from cattle_health_app.behavior.external_clips import MANIFEST_FIELDS
from cattle_health_app.behavior.quality import frame_quality, track_quality


class ExternalVideoError(ValueError):
    pass


@dataclass(frozen=True)
class ExternalVideoSample:
    sample_id: str
    source_group_id: str
    source_video_id: str
    source_video_path: str
    start_second: float
    end_second: float
    crop_box: Tuple[float, float, float, float]
    mapped_label: str
    mapping_tier: str
    source_labels: Tuple[str, ...]
    source_sha256: str


@dataclass(frozen=True)
class DecodedVirtualClip:
    sample: ExternalVideoSample
    frames: Tuple[np.ndarray, ...]
    frame_indices: Tuple[int, ...]
    label_id: int


def _inside(root: Path, relative: str, field: str) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise ExternalVideoError("{} must stay inside project_root".format(field))
    raw = Path(relative)
    if raw.is_absolute() or ".." in raw.parts:
        raise ExternalVideoError("{} must stay inside project_root".format(field))
    candidate = (root / raw).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ExternalVideoError("{} must stay inside project_root".format(field)) from exc
    return candidate


def _json_tuple(raw, field: str, expected_length=None):
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ExternalVideoError("{} must be valid JSON".format(field)) from exc
    if not isinstance(value, list) or (
        expected_length is not None and len(value) != expected_length
    ):
        raise ExternalVideoError("{} has an invalid list shape".format(field))
    return tuple(value)


def load_external_samples(manifest_path, project_root) -> Tuple[ExternalVideoSample, ...]:
    root = Path(project_root).expanduser().resolve()
    samples = []
    sample_ids = set()
    try:
        handle = Path(manifest_path).open("r", encoding="utf-8-sig", newline="")
    except OSError as exc:
        raise ExternalVideoError("could not read external manifest") from exc
    with handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != MANIFEST_FIELDS:
            raise ExternalVideoError("external manifest schema is invalid")
        for line_number, row in enumerate(reader, start=2):
            try:
                if None in row:
                    raise ExternalVideoError("row contains extra values")
                sample_id = row["sample_id"].strip()
                if not sample_id or sample_id in sample_ids:
                    raise ExternalVideoError("sample_id must be unique and non-empty")
                if row["split"] != "test":
                    raise ExternalVideoError("external manifest must be test-only")
                if row["mapping_tier"] not in {"strict", "extended"}:
                    raise ExternalVideoError("mapping_tier must be strict or extended")
                mapped_label = row["mapped_label"]
                if mapped_label not in CVB_NAME_TO_ID:
                    raise ExternalVideoError("mapped_label is absent from the CVB label space")
                source = _inside(root, row["source_video_path"], "source_video_path")
                output = _inside(root, row["output_path"], "output_path")
                if source != output:
                    raise ExternalVideoError("virtual clip output_path must equal source_video_path")
                start = float(row["start_second"])
                end = float(row["end_second"])
                if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end <= start:
                    raise ExternalVideoError("clip time range is invalid")
                crop = tuple(float(value) for value in _json_tuple(row["crop_box"], "crop_box", 4))
                x1, y1, x2, y2 = crop
                if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
                    raise ExternalVideoError("crop_box must be normalized")
                labels = _json_tuple(row["source_labels"], "source_labels")
                if not labels or any(not isinstance(value, str) or not value for value in labels):
                    raise ExternalVideoError("source_labels must contain text")
                digest = row["output_sha256"].lower()
                if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                    raise ExternalVideoError("output SHA-256 is invalid")
                samples.append(
                    ExternalVideoSample(
                        sample_id=sample_id,
                        source_group_id=row["source_group_id"],
                        source_video_id=row["source_video_id"],
                        source_video_path=row["source_video_path"],
                        start_second=start,
                        end_second=end,
                        crop_box=crop,
                        mapped_label=mapped_label,
                        mapping_tier=row["mapping_tier"],
                        source_labels=labels,
                        source_sha256=digest,
                    )
                )
                sample_ids.add(sample_id)
            except (KeyError, TypeError, ValueError) as exc:
                if isinstance(exc, ExternalVideoError):
                    raise ExternalVideoError(
                        "invalid external manifest row {}: {}".format(line_number, exc)
                    ) from exc
                raise ExternalVideoError(
                    "invalid external manifest row {}: {}".format(line_number, exc)
                ) from exc
    if not samples:
        raise ExternalVideoError("external manifest must contain samples")
    return tuple(samples)


@lru_cache(maxsize=1024)
def _cached_sha256(path_text: str, size: int, modified_ns: int) -> str:
    digest = hashlib.sha256()
    with Path(path_text).open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _verified_source(sample: ExternalVideoSample, root: Path) -> Path:
    path = _inside(root, sample.source_video_path, "source_video_path")
    try:
        stat = path.stat()
    except OSError as exc:
        raise ExternalVideoError("source video is missing") from exc
    actual = _cached_sha256(str(path), stat.st_size, stat.st_mtime_ns)
    if actual != sample.source_sha256:
        raise ExternalVideoError(
            "source video SHA-256 mismatch for {}".format(sample.sample_id)
        )
    return path


def decode_virtual_clip(
    sample: ExternalVideoSample,
    project_root,
    frame_count: int = 16,
    context: float = 0.15,
) -> DecodedVirtualClip:
    if isinstance(frame_count, bool) or not isinstance(frame_count, int) or frame_count <= 1:
        raise ExternalVideoError("frame_count must be an integer greater than one")
    root = Path(project_root).expanduser().resolve()
    source = _verified_source(sample, root)
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise ExternalVideoError("could not open source video")
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if not math.isfinite(fps) or fps <= 0 or total_frames < frame_count:
            raise ExternalVideoError("source video metadata is invalid")
        duration = total_frames / fps
        start = min(sample.start_second, max(0.0, duration - frame_count / fps))
        end = min(sample.end_second, duration)
        if end <= start:
            raise ExternalVideoError("clip window falls outside source video")
        target_times = np.linspace(start, end, num=frame_count, endpoint=False)
        indices = tuple(
            min(total_frames - 1, max(0, int(round(time * fps))))
            for time in target_times
        )
        if any(current <= previous for previous, current in zip(indices, indices[1:])):
            raise ExternalVideoError("clip window cannot provide distinct model frames")
        expanded = expand_normalized_box(sample.crop_box, context)
        frames = []
        for frame_index in indices:
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, image = capture.read()
            if not ok or image is None or image.ndim != 3 or image.shape[2] != 3:
                raise ExternalVideoError("could not decode a requested source frame")
            height, width = image.shape[:2]
            x1 = max(0, min(width - 1, int(math.floor(expanded[0] * width))))
            y1 = max(0, min(height - 1, int(math.floor(expanded[1] * height))))
            x2 = max(x1 + 1, min(width, int(math.ceil(expanded[2] * width))))
            y2 = max(y1 + 1, min(height, int(math.ceil(expanded[3] * height))))
            crop = image[y1:y2, x1:x2]
            if crop.size == 0:
                raise ExternalVideoError("decoded crop is empty")
            frames.append(crop)
    finally:
        capture.release()
    return DecodedVirtualClip(
        sample=sample,
        frames=tuple(frames),
        frame_indices=indices,
        label_id=CVB_NAME_TO_ID[sample.mapped_label] - 1,
    )


def measure_virtual_clip_quality(decoded: DecodedVirtualClip) -> Mapping[str, float]:
    frame_rows = tuple(frame_quality(frame) for frame in decoded.frames)
    track = track_quality(
        tuple(range(len(decoded.frames))),
        (decoded.sample.crop_box,) * len(decoded.frames),
    )
    return {
        "frame_count": len(decoded.frames),
        "mean_brightness": float(np.mean([row.mean_brightness for row in frame_rows])),
        "mean_dark_ratio": float(np.mean([row.dark_ratio for row in frame_rows])),
        "mean_overexposed_ratio": float(
            np.mean([row.overexposed_ratio for row in frame_rows])
        ),
        "mean_laplacian_variance": float(
            np.mean([row.laplacian_variance for row in frame_rows])
        ),
        "track_continuity": track.continuity,
        "track_truncation_ratio": track.truncation_ratio,
        "track_area_stability": track.area_stability,
    }

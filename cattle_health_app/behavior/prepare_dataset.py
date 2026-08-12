from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4

from cattle_health_app.behavior.clip_extractor import (
    ClipConfig,
    ClipRejected,
    extract_clip,
)
from cattle_health_app.behavior.manifests import load_source_segments
from cattle_health_app.behavior.splitting import (
    assign_group_splits,
    iter_windows,
    stable_clip_id,
)
from cattle_health_app.behavior.tracks import (
    load_track_observations,
    select_track_id,
)


class DatasetPreparationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ClipRecord:
    clip_id: str
    segment_id: str
    source_id: str
    group_id: str
    source_cattle_id: str
    track_id: int
    start_second: float
    end_second: float
    label: str
    split: str
    relative_path: str
    frame_count: int
    observed_ratio: float
    mean_tracking_confidence: float
    selection_method: str
    dataset: str
    license: str


@dataclass(frozen=True)
class RejectedWindow:
    segment_id: str
    source_id: str
    start_second: float
    end_second: float
    label: str
    reason: str


@dataclass(frozen=True)
class PreparationResult:
    output_root: Path
    clip_count: int
    rejected_count: int


def _write_csv(path: Path, records, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(asdict(record))


def _quality_report(clips, rejected, config, seed):
    group_splits = {}
    leakage = False
    for clip in clips:
        previous = group_splits.setdefault(clip.group_id, clip.split)
        if previous != clip.split:
            leakage = True
    return {
        "schema_version": 1,
        "seed": seed,
        "config": asdict(config),
        "clip_count": len(clips),
        "rejected_count": len(rejected),
        "group_count": len(group_splits),
        "group_leakage": leakage,
        "counts_by_split": dict(
            sorted(Counter(clip.split for clip in clips).items())
        ),
        "counts_by_label": dict(
            sorted(Counter(clip.label for clip in clips).items())
        ),
        "rejections_by_reason": dict(
            sorted(Counter(item.reason for item in rejected).items())
        ),
    }


def _safe_replace(staging: Path, output: Path, overwrite: bool):
    resolved = output.resolve()
    unsafe_roots = {
        Path.cwd().resolve(),
        Path.home().resolve(),
    }
    if resolved == resolved.parent or resolved in unsafe_roots:
        raise DatasetPreparationError(f"Unsafe output directory: {resolved}")
    if output.exists():
        if not overwrite:
            raise DatasetPreparationError(
                f"Output directory already exists: {output}"
            )
        if output.is_file():
            raise DatasetPreparationError(f"Output path is a file: {output}")
        shutil.rmtree(output)
    staging.replace(output)


def prepare_dataset(
    manifest_path: str | Path,
    output_root: str | Path,
    seed: int = 20260730,
    config: ClipConfig | None = None,
    overwrite: bool = False,
) -> PreparationResult:
    config = config or ClipConfig()
    manifest = Path(manifest_path).resolve()
    output = Path(output_root).resolve()
    if output.exists() and not overwrite:
        raise DatasetPreparationError(
            f"Output directory already exists: {output}"
        )
    segments = load_source_segments(manifest)
    trainable = [segment for segment in segments if segment.label != "unknown"]
    split_by_group = assign_group_splits(
        (segment.group_id for segment in trainable),
        seed,
    )
    staging = output.parent / f".{output.name}.staging-{uuid4().hex}"
    clips = []
    rejected = []
    trajectory_cache = {}
    try:
        for segment in sorted(trainable, key=lambda item: item.segment_id):
            try:
                if segment.trajectory_path not in trajectory_cache:
                    trajectory_cache[segment.trajectory_path] = (
                        load_track_observations(segment.trajectory_path)
                    )
                observations = trajectory_cache[segment.trajectory_path]
                track_id, selection_method = select_track_id(
                    observations,
                    segment.start_second,
                    segment.end_second,
                    segment.reviewed_track_id,
                )
            except (OSError, ValueError) as error:
                rejected.append(
                    RejectedWindow(
                        segment.segment_id,
                        segment.source_id,
                        segment.start_second,
                        segment.end_second,
                        segment.label,
                        f"source:{error}",
                    )
                )
                continue

            windows = list(
                iter_windows(
                    segment.start_second,
                    segment.end_second,
                    config.window_seconds,
                    config.stride_seconds,
                )
            )
            if not windows:
                rejected.append(
                    RejectedWindow(
                        segment.segment_id,
                        segment.source_id,
                        segment.start_second,
                        segment.end_second,
                        segment.label,
                        "segment_shorter_than_window",
                    )
                )
                continue

            for start_second, end_second in windows:
                clip_id = stable_clip_id(
                    segment.segment_id,
                    segment.source_id,
                    track_id,
                    start_second,
                    end_second,
                    segment.label,
                )
                relative_path = (
                    Path("clips")
                    / split_by_group[segment.group_id]
                    / segment.label
                    / f"{clip_id}.mp4"
                )
                try:
                    extracted = extract_clip(
                        segment.video_path,
                        observations,
                        track_id,
                        start_second,
                        end_second,
                        staging / relative_path,
                        config,
                    )
                except (ClipRejected, OSError, ValueError) as error:
                    rejected.append(
                        RejectedWindow(
                            segment.segment_id,
                            segment.source_id,
                            start_second,
                            end_second,
                            segment.label,
                            str(error),
                        )
                    )
                    continue
                clips.append(
                    ClipRecord(
                        clip_id=clip_id,
                        segment_id=segment.segment_id,
                        source_id=segment.source_id,
                        group_id=segment.group_id,
                        source_cattle_id=segment.cattle_id,
                        track_id=track_id,
                        start_second=start_second,
                        end_second=end_second,
                        label=segment.label,
                        split=split_by_group[segment.group_id],
                        relative_path=relative_path.as_posix(),
                        frame_count=extracted.frame_count,
                        observed_ratio=extracted.observed_ratio,
                        mean_tracking_confidence=(
                            extracted.mean_tracking_confidence
                        ),
                        selection_method=selection_method,
                        dataset=segment.dataset,
                        license=segment.license,
                    )
                )

        if not clips:
            raise DatasetPreparationError(
                "No valid behavior clips were generated"
            )
        clips.sort(key=lambda item: item.clip_id)
        rejected.sort(
            key=lambda item: (
                item.segment_id,
                item.start_second,
                item.reason,
            )
        )
        manifest_copy = staging / "manifests" / "source_segments.csv"
        manifest_copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(manifest, manifest_copy)
        _write_csv(
            staging / "manifests" / "clips.csv",
            clips,
            list(ClipRecord.__dataclass_fields__),
        )
        _write_csv(
            staging / "reports" / "rejected_windows.csv",
            rejected,
            list(RejectedWindow.__dataclass_fields__),
        )
        report = _quality_report(clips, rejected, config, seed)
        if report["group_leakage"]:
            raise DatasetPreparationError("Group leakage detected")
        report_path = staging / "reports" / "quality_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _safe_replace(staging, output, overwrite)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return PreparationResult(output, len(clips), len(rejected))


def parse_args():
    parser = argparse.ArgumentParser(
        description="Prepare leakage-safe single-cattle behavior clips."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260730)
    parser.add_argument("--window-seconds", type=float, default=4.0)
    parser.add_argument("--stride-seconds", type=float, default=2.0)
    parser.add_argument("--target-fps", type=float, default=12.0)
    parser.add_argument("--output-size", type=int, default=224)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    config = ClipConfig(
        window_seconds=args.window_seconds,
        stride_seconds=args.stride_seconds,
        target_fps=args.target_fps,
        output_size=args.output_size,
    )
    result = prepare_dataset(
        args.manifest,
        args.output,
        seed=args.seed,
        config=config,
        overwrite=args.overwrite,
    )
    print(
        json.dumps(
            {
                "output_root": str(result.output_root),
                "clip_count": result.clip_count,
                "rejected_count": result.rejected_count,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

# Behavior Dataset Preparation

This command prepares research clips. It does not diagnose cattle disease and
does not train the behavior model.

## Required source manifest

The UTF-8 CSV header is:

```text
segment_id,source_id,video_path,trajectory_path,dataset,license,group_id,cattle_id,track_id,start_second,end_second,label
```

`segment_id` identifies one annotation interval. `source_id` identifies the
original video and may repeat. `group_id` is the stable cattle identity when
known, otherwise the original video identity. `track_id` is the optional
reviewed ByteTrack identity and is not the same as `cattle_id`.

Allowed labels are `feeding`, `lying`, `standing`, `walking`, and `unknown`.
Unknown segments are retained in the reviewed source manifest but are excluded
from training clips.

Every source row must contain the concrete dataset name and license. Relative
video and trajectory paths are resolved from the source manifest directory.

## Run

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' `
  -m cattle_health_app.behavior.prepare_dataset `
  --manifest data\behavior_sources\source_segments.csv `
  --output data\behavior_v1 `
  --seed 20260730
```

The default extractor writes four-second, 12 FPS, 224 x 224 single-cattle clips
with a 15 percent context margin. Groups are assigned to train, validation, and
test before clips are generated, so clips from the same source group cannot
leak across splits.

The output contains:

```text
data/behavior_v1/
  clips/train/<label>/*.mp4
  clips/val/<label>/*.mp4
  clips/test/<label>/*.mp4
  manifests/source_segments.csv
  manifests/clips.csv
  reports/rejected_windows.csv
  reports/quality_report.json
```

Do not use `--overwrite` until the existing output has been backed up. Splits
must be made by group, never by individual frames or generated clips.

## Quality review

Before training X3D:

1. Confirm `group_leakage` is `false` in `quality_report.json`.
2. Review counts by split, label, and rejection reason.
3. Open a sample from every class and split.
4. Confirm the selected animal remains visible throughout each clip.
5. Confirm dataset and license fields are present in `clips.csv`.

The initial trainable vocabulary intentionally remains limited to feeding,
lying, standing, and walking. Add another class only after its annotation and
license have been reviewed.

## External cross-domain benchmark

The CVB → CBVD-5 experiment is a test-only robustness benchmark. It does not
add CBVD-5 clips to CVB training and does not use external labels to fit the
temperature, rejection thresholds, or quality rules.

- Dataset: CBVD-5 Kaggle version 11, CC0 Public Domain.
- Local media: `data/external/cbvd5/raw/videos/videos/` (687 MP4 files,
  3,480,105,107 bytes; ignored by Git).
- Auditable manifests: `data/external/cbvd5/manifests/`.
- Strict external test: 400 clips, four classes, 211 source videos.
- Extended external test: 600 clips, six classes, 298 source videos.
- Compact results and defense figures:
  `outputs/cross_domain/cvb_to_cbvd5/`.
- Full provenance and operations ledger:
  `docs/data/2026-08-23-public-cattle-video-data-record.md`.
- Scientific results and claim boundaries:
  `docs/experiments/2026-08-23-cross-domain-behavior-results.md`.

The frozen zero-shot result is a failure boundary, not a deployment claim:
strict Macro-F1 is 0.0048 on 400 samples. Fixed confidence/entropy rejection
and the predeclared heuristic quality guard do not provide meaningful risk
improvement. Do not retune those policies on CBVD-5. The recorded Go/No-Go
decision permits only a new, source-group-isolated few-shot adaptation plan.

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -X utf8 `
  -m scripts.run_cross_domain_behavior_experiment `
  --manifest data/external/cbvd5/manifests/evaluation_clips_strict.csv `
  --manifest data/external/cbvd5/manifests/evaluation_clips_extended.csv `
  --output outputs/cross_domain/cvb_to_cbvd5 `
  --checkpoint models/behavior/cvb_x3d_v2_best.pt `
  --calibration models/behavior/cvb_x3d_v2_calibration.json `
  --project-root . --device cuda --batch-size 4 `
  --stress-per-class 20 --stress-levels 0,1,2,3 `
  --seed 20260823 --resume
```

VLM, RGB plus thermal imaging, and embodied-device integration remain the last
future-research stage. They are not part of the completed benchmark and must
not be presented as current experimental results.

# CVB Full Behavior Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Train a 12-label CVB X3D behavior classifier and integrate per-track behavior labels, confidence, statistics, and artifacts into the existing uploaded-video workflow.

**Architecture:** Keep the existing YOLO detector and ByteTrack association. Build leakage-safe per-cattle frame-clip indexes from CVB AVA annotations, fine-tune an X3D model, then attach a bounded clip buffer and temporal smoother to each active track in `tracking_pipeline.py`. Preserve the existing health-only fallback when behavior weights are unavailable.

**Tech Stack:** Python 3.8, PyTorch 2.0, PyTorchVideo X3D, OpenCV, pandas, scikit-learn, Ultralytics/ByteTrack, FastAPI, React 18, TypeScript, Vitest, pytest.

---

## File map

New focused modules:

- `cattle_health_app/behavior/cvb_labels.py`: authoritative CVB IDs, English names, Chinese display names, and uncertainty policy.
- `cattle_health_app/behavior/cvb_index.py`: parse AVA CSV rows, map frame folders, reject unavailable data, and create group-safe manifests.
- `cattle_health_app/behavior/dataset.py`: load indexed 16-frame cattle crops and apply train/evaluation transforms.
- `cattle_health_app/behavior/model.py`: construct X3D, replace its head, and load versioned behavior checkpoints.
- `cattle_health_app/behavior/train.py`: reproducible training/evaluation CLI, metrics, early stopping, AMP, and resume.
- `cattle_health_app/behavior/runtime.py`: per-track buffers, batched inference, confidence thresholding, and temporal smoothing.
- `cattle_health_app/behavior/reporting.py`: behavior CSV and per-track summary generation.
- `scripts/prepare_cvb_behavior.ps1`: fixed F-drive data-index command.
- `scripts/train_cvb_behavior.ps1`: fixed Conda environment and F-drive training/cache command.

Modified integration files:

- `cattle_health_app/behavior/labels.py`: retain legacy four-label API while exporting the CVB vocabulary.
- `cattle_health_app/tracking_pipeline.py`: feed tracked crops to the behavior runtime, render labels, and return behavior artifacts.
- `cattle_health_app/media_processor.py`: resolve and lazily load optional behavior weights.
- `cattle_health_app/model_registry.py`: resolve behavior checkpoint and expose unavailable status without breaking detector startup.
- `cattle_health_app/api.py`: include behavior model status in `/api/models`.
- `run_api.py`: pass the default behavior checkpoint path.
- `web/src/api.ts`: type the new result and model fields.
- `web/src/RecognitionStudio.tsx`: display behavior summary and artifact download.
- `web/src/styles.css`: behavior table and fallback-state styling.
- `README_BEHAVIOR_DATA.md`: document CVB preparation, training, evaluation, and inference.
- `requirements.txt`: pin PyTorchVideo and metric dependencies compatible with the existing Python 3.8 environment.

## Task 1: Add the authoritative 12-label vocabulary

**Files:**
- Create: `cattle_health_app/behavior/cvb_labels.py`
- Modify: `cattle_health_app/behavior/labels.py`
- Modify: `cattle_health_app/behavior/__init__.py`
- Test: `delivery_tests/test_cvb_labels.py`

- [ ] **Step 1: Write the failing label-policy tests**

```python
from cattle_health_app.behavior.cvb_labels import (
    CVB_LABELS,
    behavior_display,
    health_eligible,
)


def test_cvb_ids_match_official_pbtx_order():
    assert list(CVB_LABELS) == list(range(1, 13))
    assert CVB_LABELS[2].name == "grazing"
    assert CVB_LABELS[12].name == "running"


def test_uncertain_labels_share_display_and_are_health_ineligible():
    for label_id in (1, 10, 11):
        assert behavior_display(label_id) == "无法确定"
        assert health_eligible(label_id) is False
    assert health_eligible(8) is True
```

- [ ] **Step 2: Run the tests and verify the module is missing**

Run: `& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_cvb_labels.py -q`

Expected: collection fails with `ModuleNotFoundError: cattle_health_app.behavior.cvb_labels`.

- [ ] **Step 3: Implement immutable label metadata and compatibility exports**

```python
# cattle_health_app/behavior/cvb_labels.py
from dataclasses import dataclass


@dataclass(frozen=True)
class BehaviorLabel:
    id: int
    name: str
    display_name: str
    uncertain: bool = False


_ROWS = (
    (1, "none", "无法确定", True),
    (2, "grazing", "采食", False),
    (3, "walking", "行走", False),
    (4, "ruminating-standing", "站立反刍", False),
    (5, "ruminating-lying", "卧姿反刍", False),
    (6, "resting-standing", "站立休息", False),
    (7, "resting-lying", "卧姿休息", False),
    (8, "drinking", "饮水", False),
    (9, "grooming", "梳理", False),
    (10, "other", "无法确定", True),
    (11, "hidden", "无法确定", True),
    (12, "running", "奔跑", False),
)
CVB_LABELS = {row[0]: BehaviorLabel(*row) for row in _ROWS}
CVB_NAME_TO_ID = {item.name: item.id for item in CVB_LABELS.values()}


def behavior_display(label_id: int) -> str:
    return CVB_LABELS[label_id].display_name


def health_eligible(label_id: int) -> bool:
    return not CVB_LABELS[label_id].uncertain
```

Export `CVB_LABELS`, `CVB_NAME_TO_ID`, `behavior_display`, and `health_eligible` from `behavior/__init__.py`. Do not delete `TRAINABLE_LABELS` or `canonical_label`; existing four-label dataset tests must remain valid.

- [ ] **Step 4: Run old and new label tests**

Run: `& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_behavior_labels.py delivery_tests/test_cvb_labels.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit the vocabulary**

```powershell
git add cattle_health_app/behavior/cvb_labels.py cattle_health_app/behavior/labels.py cattle_health_app/behavior/__init__.py delivery_tests/test_cvb_labels.py
git commit -m "feat: add CVB behavior vocabulary"
```

## Task 2: Parse CVB AVA annotations into leakage-safe sample indexes

**Files:**
- Create: `cattle_health_app/behavior/cvb_index.py`
- Create: `delivery_tests/test_cvb_index.py`
- Create: `scripts/prepare_cvb_behavior.ps1`
- Modify: `.gitignore`

- [ ] **Step 1: Write failing parser and split tests with a tiny synthetic CVB tree**

```python
import csv
from pathlib import Path

from cattle_health_app.behavior.cvb_index import build_cvb_index


def test_build_index_filters_partial_frames_and_preserves_groups(tmp_path):
    data = tmp_path / "data"
    frames = data / "raw_frames" / "clip_a"
    frames.mkdir(parents=True)
    for number in range(1, 18):
        (frames / f"img_{number:05d}.jpg").write_bytes(b"jpg")
    (frames / "img_00009.jpg.aria2").write_bytes(b"resume")
    ava = data / "ava.csv"
    ava.write_text("clip_a,01,0.1,0.2,0.8,0.9,2,7\n", encoding="utf-8")

    result = build_cvb_index(data, ava, tmp_path / "out", split="train")

    assert result.accepted == 0
    assert result.rejected_by_reason["partial_frame"] == 1
```

Add a second test with two complete clips from the same source prefix and assert every row shares the same `group_id` and assigned split.

- [ ] **Step 2: Run and verify failure**

Run: `& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_cvb_index.py -q`

Expected: import failure for `cvb_index`.

- [ ] **Step 3: Implement strict AVA parsing and quality reporting**

Create dataclasses `AvaAnnotation`, `IndexedClip`, and `IndexResult`. Implement:

```python
def parse_ava_row(row: list[str]) -> AvaAnnotation:
    if len(row) != 8:
        raise ValueError(f"Expected 8 AVA columns, got {len(row)}")
    video_id, timestamp, x1, y1, x2, y2, label_id, track_id = row
    label_id = int(label_id)
    if label_id not in CVB_LABELS:
        raise ValueError(f"Unknown CVB label id: {label_id}")
    return AvaAnnotation(
        video_id=video_id,
        center_frame=max(1, int(timestamp)),
        bbox=tuple(map(float, (x1, y1, x2, y2))),
        label_id=label_id,
        track_id=int(track_id),
    )
```

`build_cvb_index` must deduplicate identical AVA rows, require 16 decodable source frames around the center, reject any target with an adjacent `.aria2`, group by the original recording portion of `video_id`, and write UTF-8 `train.csv`, `val.csv`, `test.csv`, `rejected.csv`, and `quality_report.json`. Use official `ava_val_set.csv` only for `test`; deterministically divide official train groups into train/val with seed `20260814`.

- [ ] **Step 4: Add the fixed preparation script**

```powershell
$ErrorActionPreference = 'Stop'
$python = 'F:\deepl\anaconda1\envs\pytorch\python.exe'
$data = 'F:\CVB_dataset\000058916v001\data'
$output = 'F:\new大创\data\cvb_behavior_v1'
& $python -m cattle_health_app.behavior.cvb_index `
  --data-root $data `
  --train-ava "$data\cvb_in_ava_format\ava_train_set.csv" `
  --test-ava "$data\cvb_in_ava_format\ava_val_set.csv" `
  --output $output `
  --seed 20260814
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
```

Ignore `data/cvb_behavior_v1/` in Git while retaining generated JSON/CSV as local training artifacts.

- [ ] **Step 5: Run parser tests and legacy behavior tests**

Run: `& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_cvb_index.py delivery_tests/test_behavior_splitting.py delivery_tests/test_behavior_prepare_dataset.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit index preparation**

```powershell
git add cattle_health_app/behavior/cvb_index.py delivery_tests/test_cvb_index.py scripts/prepare_cvb_behavior.ps1 .gitignore
git commit -m "feat: index CVB behavior annotations"
```

## Task 3: Build the indexed 16-frame crop dataset

**Files:**
- Create: `cattle_health_app/behavior/dataset.py`
- Create: `delivery_tests/test_cvb_dataset.py`

- [ ] **Step 1: Write failing crop, shape, and label tests**

```python
import cv2
import numpy as np
import torch

from cattle_health_app.behavior.dataset import CvbClipDataset


def test_dataset_returns_normalized_cthw_clip(tmp_path, indexed_manifest):
    dataset = CvbClipDataset(indexed_manifest, training=False)
    clip, target = dataset[0]
    assert clip.shape == (3, 16, 224, 224)
    assert clip.dtype == torch.float32
    assert target == 1  # official label id 2 becomes zero-based class index 1
    assert torch.isfinite(clip).all()
```

The `indexed_manifest` fixture must generate 16 real JPEGs with a known normalized box so the test also asserts the colored cow region remains inside the crop.

- [ ] **Step 2: Run and verify failure**

Run: `& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_cvb_dataset.py -q`

Expected: import failure for `dataset`.

- [ ] **Step 3: Implement indexed loading and transforms**

Implement `ClipSample`, `load_index`, `expand_normalized_box`, and `CvbClipDataset`. The dataset must decode exactly the indexed paths, crop each frame with 15% context, letterbox to 224, stack to `C,T,H,W`, scale to `[0,1]`, normalize with Kinetics mean/std, and return `label_id - 1`. Training-only augmentation is horizontal flip and mild color jitter; do not use temporal reversal because behavior direction and motion must remain natural.

```python
KINETICS_MEAN = torch.tensor([0.45, 0.45, 0.45]).view(3, 1, 1, 1)
KINETICS_STD = torch.tensor([0.225, 0.225, 0.225]).view(3, 1, 1, 1)


def normalize_clip(clip: torch.Tensor) -> torch.Tensor:
    return (clip.float().div(255.0) - KINETICS_MEAN) / KINETICS_STD
```

Raise `UnreadableClipError` containing the sample ID and offending path; the indexer should prevent these during normal training.

- [ ] **Step 4: Run dataset tests**

Run: `& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_cvb_dataset.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit the dataset loader**

```powershell
git add cattle_health_app/behavior/dataset.py delivery_tests/test_cvb_dataset.py
git commit -m "feat: load indexed CVB video clips"
```

## Task 4: Add X3D construction and versioned checkpoint loading

**Files:**
- Create: `cattle_health_app/behavior/model.py`
- Create: `delivery_tests/test_behavior_model.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Write failing model and checkpoint tests**

```python
import torch

from cattle_health_app.behavior.model import build_x3d, load_behavior_checkpoint


def test_x3d_emits_twelve_logits():
    model = build_x3d(num_classes=12, pretrained=False)
    with torch.inference_mode():
        logits = model(torch.zeros(1, 3, 16, 224, 224))
    assert logits.shape == (1, 12)


def test_checkpoint_rejects_wrong_label_order(tmp_path):
    path = tmp_path / "bad.pt"
    torch.save({"state_dict": {}, "labels": ["wrong"]}, path)
    try:
        load_behavior_checkpoint(path, device="cpu")
    except ValueError as error:
        assert "label" in str(error).lower()
    else:
        raise AssertionError("wrong label metadata was accepted")
```

- [ ] **Step 2: Run and verify failure**

Run: `& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_behavior_model.py -q`

Expected: import failure for `model`.

- [ ] **Step 3: Pin compatible dependencies and implement the model API**

Add:

```text
pytorchvideo==0.1.5
fvcore==0.1.5.post20221221
iopath==0.1.10
scikit-learn==1.3.2
```

Implement `build_x3d(num_classes=12, pretrained=True)` using the PyTorchVideo X3D-XS builder or Kinetics checkpoint. Replace only the final projection with 12 outputs. Implement `BehaviorCheckpoint` metadata and save/load helpers with this required payload:

```python
{
    "format_version": 1,
    "architecture": "x3d_xs",
    "labels": [CVB_LABELS[index].name for index in range(1, 13)],
    "input_frames": 16,
    "input_size": 224,
    "state_dict": model.state_dict(),
    "metrics": metrics,
    "training_config": config,
}
```

Loading must use `map_location`, verify every metadata field, and return a model in evaluation mode.

- [ ] **Step 4: Install only the new pinned packages into the existing F-drive environment**

Run:

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pip install `
  pytorchvideo==0.1.5 fvcore==0.1.5.post20221221 `
  iopath==0.1.10 scikit-learn==1.3.2
```

Expected: successful install without replacing `torch==2.0.0`.

- [ ] **Step 5: Run model tests on CPU**

Run: `& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_behavior_model.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit model support**

```powershell
git add requirements.txt cattle_health_app/behavior/model.py delivery_tests/test_behavior_model.py
git commit -m "feat: add X3D behavior model"
```

## Task 5: Implement reproducible training, metrics, resume, and evaluation

**Files:**
- Create: `cattle_health_app/behavior/train.py`
- Create: `delivery_tests/test_behavior_training.py`
- Create: `scripts/train_cvb_behavior.ps1`

- [ ] **Step 1: Write failing tests for weighted loss, metrics, and resume state**

```python
import torch

from cattle_health_app.behavior.train import compute_metrics, make_class_weights


def test_macro_f1_counts_rare_classes():
    metrics = compute_metrics([0, 1, 2, 2], [0, 1, 1, 2], class_count=3)
    assert 0 < metrics["macro_f1"] < 1
    assert len(metrics["per_class"]) == 3


def test_class_weights_are_finite_for_present_classes():
    weights = make_class_weights([20, 10, 5])
    assert weights.shape == (3,)
    assert torch.isfinite(weights).all()
    assert weights[2] > weights[0]
```

Add a checkpoint round-trip test asserting restored epoch, optimizer state, scaler state, best Macro-F1, and training configuration.

- [ ] **Step 2: Run and verify failure**

Run: `& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_behavior_training.py -q`

Expected: import failure for `train`.

- [ ] **Step 3: Implement the training engine and CLI**

Implement `TrainingConfig`, `seed_everything`, `make_loaders`, `train_epoch`, `evaluate`, `compute_metrics`, `save_training_state`, and `run_training`. Required defaults:

```python
TrainingConfig(
    epochs=30,
    batch_size=4,
    accumulation_steps=4,
    learning_rate=3e-4,
    weight_decay=1e-4,
    patience=6,
    workers=2,
    seed=20260814,
    amp=True,
)
```

Use cross-entropy with one inverse-frequency class-weight mechanism, `AdamW`, cosine scheduling, `torch.cuda.amp`, gradient clipping at 5.0, and early stopping on validation Macro-F1. Save `last.pt` every epoch and replace `best.pt` only when Macro-F1 improves. Write `history.csv`, `metrics.json`, `classification_report.csv`, `confusion_matrix.csv`, `confusion_matrix.png`, and `training_curves.png`.

CLI modes must be `smoke`, `train`, and `evaluate`. `smoke` limits each split to a deterministic class-covering subset and runs two optimizer steps; `evaluate` requires an explicit checkpoint and never updates weights.

- [ ] **Step 4: Add the fixed F-drive training wrapper**

```powershell
$ErrorActionPreference = 'Stop'
$env:TORCH_HOME = 'F:\new大创\models\cache\torch'
$python = 'F:\deepl\anaconda1\envs\pytorch\python.exe'
& $python -m cattle_health_app.behavior.train `
  --mode $args[0] `
  --data-root 'F:\new大创\data\cvb_behavior_v1' `
  --output-root 'F:\new大创\outputs\training\cvb_x3d_v1' `
  --model-root 'F:\new大创\models\behavior' `
  --seed 20260814
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
```

- [ ] **Step 5: Run unit tests**

Run: `& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_behavior_training.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit training support**

```powershell
git add cattle_health_app/behavior/train.py delivery_tests/test_behavior_training.py scripts/train_cvb_behavior.ps1
git commit -m "feat: add reproducible behavior training"
```

## Task 6: Prepare real CVB indexes and run the training smoke gate

**Files:**
- Generated, not committed: `data/cvb_behavior_v1/**`
- Generated, not committed: `outputs/training/cvb_x3d_v1/**`

- [ ] **Step 1: Stop the obsolete aria2 process only if it is still running and writing no data**

Run: `Get-Process aria2c -ErrorAction SilentlyContinue | Select-Object Id,CPU,StartTime`

Expected: either no process, or record its state before deciding. Do not delete `.aria2` or completed CVB data.

- [ ] **Step 2: Build the real index**

Run: `powershell -ExecutionPolicy Bypass -File scripts/prepare_cvb_behavior.ps1`

Expected: exit 0 and `data/cvb_behavior_v1/quality_report.json` with `group_leakage: false`, non-zero rows for all 12 labels, and explicit rejected counts.

- [ ] **Step 3: Inspect quality gates**

Run:

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -c "import json; p=json.load(open(r'F:\new大创\data\cvb_behavior_v1\quality_report.json',encoding='utf-8')); assert not p['group_leakage']; assert len(p['class_counts'])==12; print(json.dumps(p,ensure_ascii=False,indent=2))"
```

Expected: assertions pass. If a class is absent, stop and correct index mapping before training.

- [ ] **Step 4: Run the CUDA smoke train**

Run: `powershell -ExecutionPolicy Bypass -File scripts/train_cvb_behavior.ps1 smoke`

Expected: two optimizer steps complete on CUDA, loss is finite, `last.pt` reloads, and peak VRAM stays below 8 GB.

- [ ] **Step 5: Record the smoke evidence**

Run: `Get-Content -Raw outputs/training/cvb_x3d_v1/smoke_metrics.json`

Expected: JSON includes device, PyTorch/CUDA versions, input shape, finite loss, peak VRAM, and reload success. Do not commit generated weights or dataset indexes.

## Task 7: Add the per-track runtime and temporal smoothing

**Files:**
- Create: `cattle_health_app/behavior/runtime.py`
- Create: `delivery_tests/test_behavior_runtime.py`

- [ ] **Step 1: Write failing buffering and smoothing tests**

```python
import numpy as np

from cattle_health_app.behavior.runtime import BehaviorRuntime


class FakeClassifier:
    def predict(self, clips):
        return [[0.01, 0.80] + [0.019] * 10 for _ in clips]


def test_runtime_waits_for_sixteen_frames_and_returns_per_track_result():
    runtime = BehaviorRuntime(FakeClassifier(), clip_frames=16, stride=4)
    for frame_index in range(15):
        assert runtime.observe(7, frame_index, np.zeros((224, 224, 3), np.uint8)) is None
    result = runtime.observe(7, 15, np.zeros((224, 224, 3), np.uint8))
    assert result.track_id == 7
    assert result.label_id == 2
    assert result.display_name == "采食"
```

Add tests that low confidence maps to uncertain, a missing track expires after a configured TTL, and exponential smoothing prevents one contradictory prediction from immediately changing the display label.

- [ ] **Step 2: Run and verify failure**

Run: `& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_behavior_runtime.py -q`

Expected: import failure for `runtime`.

- [ ] **Step 3: Implement runtime interfaces**

Implement `BehaviorPrediction`, `TrackClipBuffer`, `TorchBehaviorClassifier`, and `BehaviorRuntime`. The runtime stores at most 16 crops per track, infers every four new frames, batches ready tracks, exponentially averages probabilities with `alpha=0.4`, applies default confidence threshold `0.45`, and expires unseen tracks after `max(2 * fps, 32)` frames. Uncertain outputs use display text “无法确定” and `health_eligible=False`.

The classifier must accept BGR crops, reuse the exact evaluation transform from `dataset.py`, run under `torch.inference_mode()` and CUDA autocast, and return CPU probabilities. It must not own video decoding or tracking.

- [ ] **Step 4: Run runtime tests**

Run: `& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_behavior_runtime.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit runtime support**

```powershell
git add cattle_health_app/behavior/runtime.py delivery_tests/test_behavior_runtime.py
git commit -m "feat: infer smoothed behavior per track"
```

## Task 8: Generate behavior artifacts and integrate them into tracked video

**Files:**
- Create: `cattle_health_app/behavior/reporting.py`
- Modify: `cattle_health_app/tracking_pipeline.py`
- Modify: `delivery_tests/test_tracking_pipeline.py`
- Create: `delivery_tests/test_behavior_reporting.py`

- [ ] **Step 1: Write failing serialization and aggregation tests**

Extend `TrackingVideoResult` construction with:

```python
behavior_csv=result_dir / "behavior.csv",
behavior_summary_csv=result_dir / "behavior_summary.csv",
behavior_model_status="ready",
behavior_model_version="cvb-x3d-v1",
behavior_summary=[
    {
        "track_id": 7,
        "display_name": "采食",
        "duration_seconds": 12.5,
        "percentage": 62.5,
    }
],
```

Assert `to_dict()` returns relative behavior paths, status, version, and the JSON-safe `behavior_summary` rows. In reporting tests, feed known predictions at 20 FPS and assert eligible behavior duration is accumulated while uncertain duration is recorded separately and excluded from health behavior totals.

- [ ] **Step 2: Run and verify failure**

Run: `& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_tracking_pipeline.py delivery_tests/test_behavior_reporting.py -q`

Expected: constructor or import failures for the new fields/module.

- [ ] **Step 3: Implement behavior reporting**

Implement `BehaviorObservation`, `write_behavior_timeline`, and `write_behavior_summary`. Timeline fields are:

```text
frame_index,time_seconds,track_id,label_id,label,display_name,confidence,health_eligible,model_version
```

Summary fields are:

```text
track_id,label_id,label,display_name,duration_seconds,percentage,health_eligible,model_version
```

Percentages use the observed duration for each track as denominator and must sum to approximately 100% per track.

- [ ] **Step 4: Integrate optional behavior runtime into the tracking loop**

Add optional `behavior_runtime=None` to `process_tracked_video`. Convert each `xywh` to a clamped 15%-context crop, call the runtime by `track_id`, append returned predictions, and draw text using OpenCV above each box. Keep `result.plot()` only as the base annotated frame. If no behavior runtime is supplied, preserve current output and set `behavior_model_status="unavailable"`.

After decoding, write the two behavior CSVs and include their paths plus the parsed per-track summary rows in `TrackingVideoResult.behavior_summary`. Behavior inference exceptions must be logged once, disable only behavior for the remaining video, and allow tracking/health artifacts to finish.

- [ ] **Step 5: Run tracking and reporting tests**

Run: `& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_tracking_pipeline.py delivery_tests/test_behavior_reporting.py -q`

Expected: all tests pass, including the no-behavior fallback.

- [ ] **Step 6: Commit video integration**

```powershell
git add cattle_health_app/behavior/reporting.py cattle_health_app/tracking_pipeline.py delivery_tests/test_tracking_pipeline.py delivery_tests/test_behavior_reporting.py
git commit -m "feat: annotate tracked video with behavior"
```

## Task 9: Resolve behavior weights and expose graceful model status

**Files:**
- Modify: `cattle_health_app/model_registry.py`
- Modify: `cattle_health_app/media_processor.py`
- Modify: `cattle_health_app/api.py`
- Modify: `run_api.py`
- Modify: `delivery_tests/test_model_registry.py`
- Modify: `delivery_tests/test_delivery_api.py`
- Modify: `delivery_tests/test_video_jobs.py`

- [ ] **Step 1: Write failing optional-model tests**

Add tests asserting:

```python
assert resolve_behavior_model(tmp_path / "missing.pt").status == "unavailable"
assert client.get("/api/models").json()["behavior"]["status"] == "unavailable"
```

Update `FakeProcessor` video results to include behavior paths/status and assert job JSON preserves them.

- [ ] **Step 2: Run and verify failure**

Run: `& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_model_registry.py delivery_tests/test_delivery_api.py delivery_tests/test_video_jobs.py -q`

Expected: failures for missing behavior registry/status fields.

- [ ] **Step 3: Implement optional checkpoint resolution and lazy runtime loading**

Add a `BehaviorModelArtifact` with `name`, `path`, `sha256`, `status`, and `version`. `resolve_behavior_model` checks the explicit path, `CATTLE_BEHAVIOR_MODEL`, then `models/behavior/cvb_x3d_v1_best.pt`; unlike detector resolution, absence returns `status="unavailable"` instead of raising.

Extend `LocalMediaProcessor.__init__` with `behavior_model_path=None`, retain a separate lazy `BehaviorRuntime`, and pass it to `process_tracked_video`. The same inference lock may protect detector and behavior GPU work in the initial implementation.

Expose both detector and behavior metadata from `/api/models`. In `run_api.py`, pass `models/behavior/cvb_x3d_v1_best.pt` as the default path without requiring it to exist.

- [ ] **Step 4: Run API and job tests**

Run: `& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_model_registry.py delivery_tests/test_delivery_api.py delivery_tests/test_video_jobs.py -q`

Expected: all tests pass and detector-only startup remains supported.

- [ ] **Step 5: Commit backend model wiring**

```powershell
git add cattle_health_app/model_registry.py cattle_health_app/media_processor.py cattle_health_app/api.py run_api.py delivery_tests/test_model_registry.py delivery_tests/test_delivery_api.py delivery_tests/test_video_jobs.py
git commit -m "feat: expose optional behavior model status"
```

## Task 10: Display behavior artifacts in the upload result page

**Files:**
- Modify: `web/src/api.ts`
- Modify: `web/src/RecognitionStudio.tsx`
- Modify: `web/src/styles.css`
- Modify: `web/src/App.test.tsx`

- [ ] **Step 1: Extend the mocked completed job and write failing UI assertions**

Add to the tracking result fixture:

```typescript
behavior_csv: "job-1/cattle_behavior.csv",
behavior_summary_csv: "job-1/cattle_behavior_summary.csv",
behavior_model_status: "ready",
behavior_model_version: "cvb-x3d-v1",
behavior_summary: [
  { track_id: 7, display_name: "采食", duration_seconds: 12.5, percentage: 62.5 },
],
```

Assert the page shows `牛 7`, `采食`, `12.5 秒`, `62.5%`, the model version, and behavior CSV download links. Add another test where status is `unavailable` and assert the existing video still renders with a visible “行为模型未加载” notice.

- [ ] **Step 2: Run and verify failure**

Run: `Set-Location web; npm test -- --run src/App.test.tsx`

Expected: type or element-query failures for behavior fields.

- [ ] **Step 3: Extend API types and render the result summary**

Add:

```typescript
export type BehaviorSummaryRow = {
  track_id: number;
  display_name: string;
  duration_seconds: number;
  percentage: number;
};
```

Extend `TrackingResult` with behavior artifact paths, status, version, and `behavior_summary`. In `RecognitionStudio`, render a compact table grouped by track when status is ready, download links for both CSVs, and a non-blocking fallback callout otherwise. Keep all existing trajectory and health links.

- [ ] **Step 4: Add focused styling**

Add `.behavior-summary`, `.behavior-summary-table`, and `.behavior-unavailable` styles using the existing panel colors, responsive overflow, visible focus states, and no new dependency.

- [ ] **Step 5: Run front-end tests and production build**

Run: `Set-Location web; npm test -- --run; npm run build`

Expected: all Vitest tests pass and the TypeScript/Vite production build succeeds.

- [ ] **Step 6: Commit the UI**

```powershell
git add web/src/api.ts web/src/RecognitionStudio.tsx web/src/styles.css web/src/App.test.tsx
git commit -m "feat: show per-cattle behavior results"
```

## Task 11: Run full training, evaluate once, and install the best checkpoint

**Files:**
- Generated, not committed: `outputs/training/cvb_x3d_v1/**`
- Generated, not committed: `models/behavior/cvb_x3d_v1_best.pt`

- [ ] **Step 1: Start or resume full training**

Run: `powershell -ExecutionPolicy Bypass -File scripts/train_cvb_behavior.ps1 train`

Expected: training uses CUDA, writes `last.pt` each epoch, updates `best.pt` on Macro-F1 improvement, and early-stops or reaches 30 epochs. If interrupted, rerun the same command with resume enabled rather than deleting outputs.

- [ ] **Step 2: Evaluate the selected best checkpoint exactly once on official test data**

Run:

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m cattle_health_app.behavior.train `
  --mode evaluate `
  --data-root 'F:\new大创\data\cvb_behavior_v1' `
  --checkpoint 'F:\new大创\outputs\training\cvb_x3d_v1\best.pt' `
  --split test `
  --output-root 'F:\new大创\outputs\training\cvb_x3d_v1\test'
```

Expected: exit 0 with test Macro-F1, accuracy, per-class metrics, and confusion matrix. Do not tune hyperparameters against these test metrics.

- [ ] **Step 3: Install the verified best model without losing metadata**

Run:

```powershell
Copy-Item -LiteralPath 'F:\new大创\outputs\training\cvb_x3d_v1\best.pt' `
  -Destination 'F:\new大创\models\behavior\cvb_x3d_v1_best.pt'
```

Expected: SHA-256 of source and destination match.

- [ ] **Step 4: Record actual results in documentation**

Update `README_BEHAVIOR_DATA.md` with the exact training run ID, data quality counts, validation/test Macro-F1, per-class limitations, checkpoint SHA-256, and command to reproduce. Do not claim disease diagnosis or invent target accuracy.

- [ ] **Step 5: Commit reproducibility documentation only**

```powershell
git add README_BEHAVIOR_DATA.md
git commit -m "docs: record CVB behavior training results"
```

## Task 12: Verify the complete uploaded-video workflow

**Files:**
- Create: `delivery_tests/test_behavior_video_e2e.py`
- Modify: `README_DELIVERY.md`

- [ ] **Step 1: Add an automated short-video integration test**

Use a fake detector result and deterministic fake behavior classifier so the test does not depend on GPU quality. Assert `process_tracked_video` produces a playable MP4, trajectory CSV, behavior timeline CSV, behavior summary CSV, health artifacts, and JSON-serializable relative paths. Assert three uncertain labels never appear as health-eligible rows.

- [ ] **Step 2: Run backend regression tests**

Run: `& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest tests delivery_tests -q`

Expected: all existing and new Python tests pass.

- [ ] **Step 3: Run frontend regression and build**

Run: `Set-Location web; npm test -- --run; npm run build`

Expected: all UI tests and production build pass.

- [ ] **Step 4: Run a real uploaded MP4 through the local API**

Start with `启动项目.bat`, upload a short cattle MP4 in the video-recognition page, and wait for completion. Verify the result video visibly contains per-cattle ID, Chinese behavior, and confidence; behavior CSVs download; the UI shows per-track durations; and `/api/models` reports the installed checkpoint SHA/version.

- [ ] **Step 5: Verify detector-only degradation**

Temporarily start with `CATTLE_BEHAVIOR_MODEL` pointing to a nonexistent explicit test path. Upload the same short video and verify tracking, trajectory, health CSV/HTML, and result video still complete while the UI displays “行为模型未加载”. Restore the environment variable after the test; do not move or delete the installed checkpoint.

- [ ] **Step 6: Update delivery documentation and commit**

Document the behavior model status, expected first-load delay, GPU/CPU fallback, result artifacts, and “risk screening, not diagnosis” language in `README_DELIVERY.md`.

```powershell
git add delivery_tests/test_behavior_video_e2e.py README_DELIVERY.md
git commit -m "test: verify behavior video delivery"
```

- [ ] **Step 7: Final clean-state evidence**

Run:

```powershell
git status --short
git log -12 --oneline
```

Expected: no unintended source changes; generated data, weights, caches, and output videos remain ignored/local on F drive.

# Behavior Model Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the existing CVB X3D checkpoint into uploaded-video processing so each video produces per-track behavior annotations, CSV summaries, API metadata, and a non-blocking React result view.

**Architecture:** Promote the verified label and checkpoint-loading code from `cloud_pack` into the main package, then isolate buffering/inference in a behavior runtime and aggregation in a reporting module. The tracking pipeline optionally consumes that runtime; model failure disables only behavior inference and preserves detector, tracker, trajectory, and rule-health artifacts.

**Tech Stack:** Python 3.8, PyTorch 2.0, PyTorchVideo X3D-XS, OpenCV, Ultralytics, FastAPI, pytest, React 18, TypeScript, Vitest.

---

## File map

New production files:

- `cattle_health_app/behavior/cvb_labels.py` — immutable 12-class CVB product vocabulary.
- `cattle_health_app/behavior/model.py` — X3D construction and safe versioned checkpoint loading.
- `cattle_health_app/behavior/runtime.py` — per-track frame buffering, preprocessing, inference, confidence gating, and smoothing.
- `cattle_health_app/behavior/reporting.py` — behavior timeline and summary CSV generation.

Modified production files:

- `cattle_health_app/model_registry.py` — optional behavior artifact resolution and fingerprinting.
- `cattle_health_app/media_processor.py` — lazy behavior runtime construction and detector-only degradation.
- `cattle_health_app/tracking_pipeline.py` — crop tracked cattle, request predictions, draw labels, and serialize artifacts.
- `cattle_health_app/api.py` — expose detector and behavior model metadata.
- `run_api.py` — configure the default behavior checkpoint path.
- `requirements.txt` — pin PyTorchVideo runtime dependencies.
- `web/src/api.ts` — add behavior API types.
- `web/src/RecognitionStudio.tsx` — render behavior status, summary, and downloads.
- `web/src/workspace-interactions.css` — style behavior result elements.
- `README.md` and `README_DELIVERY.md` — document the research-model boundary and operation.

New tests:

- `delivery_tests/test_behavior_model.py`
- `delivery_tests/test_behavior_runtime.py`
- `delivery_tests/test_behavior_reporting.py`
- `delivery_tests/test_behavior_video_e2e.py`

Modified tests:

- `delivery_tests/test_model_registry.py`
- `delivery_tests/test_tracking_pipeline.py`
- `delivery_tests/test_delivery_api.py`
- `delivery_tests/test_video_jobs.py`
- `delivery_tests/test_delivery_reliability.py`
- `web/src/App.test.tsx`

Generated, not committed as source code:

- `models/behavior/cvb_x3d_v2_best.pt` — installed copy of `outputs/cvb_x3d_v2/best.pt`.

## Task 1: Promote the CVB vocabulary and safe checkpoint loader

**Files:**

- Create: `cattle_health_app/behavior/cvb_labels.py`
- Create: `cattle_health_app/behavior/model.py`
- Modify: `cattle_health_app/behavior/__init__.py`
- Modify: `requirements.txt`
- Create: `delivery_tests/test_behavior_model.py`

- [ ] **Step 1: Write failing product-vocabulary and checkpoint tests**

```python
# delivery_tests/test_behavior_model.py
from pathlib import Path

import pytest
import torch

from cattle_health_app.behavior.cvb_labels import (
    CVB_LABELS,
    behavior_display,
    health_eligible,
)
from cattle_health_app.behavior.model import (
    INPUT_FRAMES,
    INPUT_SIZE,
    LABEL_ORDER,
    load_behavior_checkpoint,
)


def test_product_vocabulary_has_fixed_cvb_order():
    assert tuple(CVB_LABELS) == tuple(range(1, 13))
    assert LABEL_ORDER[0] == "none"
    assert LABEL_ORDER[-1] == "running"
    assert behavior_display(2) == "采食"
    assert health_eligible(1) is False
    assert health_eligible(10) is False
    assert health_eligible(11) is False
    assert health_eligible(8) is True
    assert INPUT_FRAMES == 16
    assert INPUT_SIZE == 224


def test_loader_rejects_missing_checkpoint(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_behavior_checkpoint(tmp_path / "missing.pt")


def test_loader_rejects_untrusted_shape(tmp_path):
    path = tmp_path / "invalid.pt"
    torch.save({"state_dict": {}}, path)
    with pytest.raises(ValueError, match="checkpoint fields"):
        load_behavior_checkpoint(path)
```

- [ ] **Step 2: Run the tests and verify the main-package modules are missing**

Run:

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_behavior_model.py -q
```

Expected: collection fails because `cattle_health_app.behavior.cvb_labels` or `.model` does not exist.

- [ ] **Step 3: Promote the exact verified model files and export their public API**

Create `cattle_health_app/behavior/cvb_labels.py` and `cattle_health_app/behavior/model.py` with the exact contents of:

- `cloud_pack/cattle_health_app/behavior/cvb_labels.py`
- `cloud_pack/cattle_health_app/behavior/model.py`

Do not import from `cloud_pack`. Update `cattle_health_app/behavior/__init__.py` to preserve its current legacy exports and add:

```python
from cattle_health_app.behavior.cvb_labels import (
    CVB_LABELS,
    CVB_NAME_TO_ID,
    BehaviorLabel,
    behavior_display,
    health_eligible,
)
```

Append these exact pins to `requirements.txt`:

```text
pytorchvideo==0.1.5
iopath==0.1.10
```

- [ ] **Step 4: Run focused and legacy behavior tests**

Run:

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_behavior_model.py delivery_tests/test_behavior_labels.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit the model foundation**

```powershell
git add cattle_health_app/behavior/cvb_labels.py cattle_health_app/behavior/model.py cattle_health_app/behavior/__init__.py requirements.txt delivery_tests/test_behavior_model.py
git commit -m "feat: add behavior checkpoint runtime foundation"
```

## Task 2: Implement per-track X3D inference and temporal smoothing

**Files:**

- Create: `cattle_health_app/behavior/runtime.py`
- Create: `delivery_tests/test_behavior_runtime.py`

- [ ] **Step 1: Write failing buffer, crop, smoothing, and confidence tests**

```python
# delivery_tests/test_behavior_runtime.py
import numpy as np
import torch

from cattle_health_app.behavior.runtime import BehaviorPrediction, BehaviorRuntime


class FakeModel(torch.nn.Module):
    def forward(self, clips):
        logits = torch.zeros((clips.shape[0], 12), device=clips.device)
        logits[:, 1] = 8.0  # zero-based class 1 => CVB id 2 => grazing
        return logits


def test_runtime_waits_for_sixteen_frames_and_isolates_tracks():
    runtime = BehaviorRuntime(FakeModel(), model_version="test-v1", device="cpu")
    frame = np.full((120, 160, 3), 127, dtype=np.uint8)
    for _ in range(15):
        assert runtime.observe(7, frame) is None
    assert runtime.observe(8, frame) is None
    prediction = runtime.observe(7, frame)
    assert isinstance(prediction, BehaviorPrediction)
    assert prediction.track_id == 7
    assert prediction.behavior_name == "grazing"
    assert prediction.display_name == "采食"
    assert prediction.health_eligible is True


def test_low_confidence_and_uncertain_labels_are_not_health_eligible():
    runtime = BehaviorRuntime(
        FakeModel(), model_version="test-v1", device="cpu", confidence_threshold=1.0
    )
    frame = np.zeros((64, 64, 3), dtype=np.uint8)
    prediction = None
    for _ in range(16):
        prediction = runtime.observe(3, frame)
    assert prediction.display_name == "无法确定"
    assert prediction.health_eligible is False


def test_crop_rejects_empty_images():
    runtime = BehaviorRuntime(FakeModel(), model_version="test-v1", device="cpu")
    assert runtime.observe(1, np.empty((0, 0, 3), dtype=np.uint8)) is None
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_behavior_runtime.py -q
```

Expected: import fails because `runtime.py` is absent.

- [ ] **Step 3: Implement the focused runtime API**

Create `cattle_health_app/behavior/runtime.py` with these public types and behavior:

```python
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict, dataclass

import cv2
import numpy as np
import torch

from cattle_health_app.behavior.cvb_labels import CVB_LABELS
from cattle_health_app.behavior.model import INPUT_FRAMES, INPUT_SIZE


@dataclass(frozen=True)
class BehaviorPrediction:
    track_id: int
    class_id: int
    behavior_name: str
    display_name: str
    confidence: float
    health_eligible: bool
    model_version: str

    def to_dict(self) -> dict:
        return asdict(self)


class BehaviorRuntime:
    def __init__(self, model, model_version, device="cpu", confidence_threshold=0.45,
                 smoothing_window=3, inference_stride=8):
        self.model = model
        self.model_version = model_version
        self.device = torch.device(device)
        self.confidence_threshold = float(confidence_threshold)
        self.inference_stride = int(inference_stride)
        self.buffers = defaultdict(lambda: deque(maxlen=INPUT_FRAMES))
        self.probabilities = defaultdict(lambda: deque(maxlen=smoothing_window))
        self.observation_counts = defaultdict(int)

    def observe(self, track_id: int, crop: np.ndarray):
        if crop.size == 0:
            return None
        resized = cv2.resize(crop, (INPUT_SIZE, INPUT_SIZE))
        self.buffers[track_id].append(cv2.cvtColor(resized, cv2.COLOR_BGR2RGB))
        self.observation_counts[track_id] += 1
        if len(self.buffers[track_id]) < INPUT_FRAMES:
            return None
        if (self.observation_counts[track_id] - INPUT_FRAMES) % self.inference_stride:
            return None
        clip = np.stack(self.buffers[track_id]).astype(np.float32) / 255.0
        tensor = torch.from_numpy(clip).permute(3, 0, 1, 2).unsqueeze(0)
        mean = torch.tensor((0.45, 0.45, 0.45)).view(1, 3, 1, 1, 1)
        std = torch.tensor((0.225, 0.225, 0.225)).view(1, 3, 1, 1, 1)
        tensor = ((tensor - mean) / std).to(self.device)
        with torch.inference_mode():
            output = self.model(tensor)
            if isinstance(output, dict):
                output = output["preds"]
            probability = torch.softmax(output, dim=1)[0].detach().cpu().numpy()
        self.probabilities[track_id].append(probability)
        smoothed = np.mean(self.probabilities[track_id], axis=0)
        zero_based = int(smoothed.argmax())
        label = CVB_LABELS[zero_based + 1]
        confidence = float(smoothed[zero_based])
        eligible = not label.uncertain and confidence >= self.confidence_threshold
        return BehaviorPrediction(
            track_id=track_id,
            class_id=label.id,
            behavior_name=label.name if eligible else "uncertain",
            display_name=label.display_name if eligible else "无法确定",
            confidence=confidence,
            health_eligible=eligible,
            model_version=self.model_version,
        )
```

- [ ] **Step 4: Run runtime tests**

Run:

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_behavior_runtime.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit the runtime**

```powershell
git add cattle_health_app/behavior/runtime.py delivery_tests/test_behavior_runtime.py
git commit -m "feat: classify buffered cattle tracks"
```

## Task 3: Generate behavior timeline and summary artifacts

**Files:**

- Create: `cattle_health_app/behavior/reporting.py`
- Create: `delivery_tests/test_behavior_reporting.py`

- [ ] **Step 1: Write failing aggregation tests**

```python
# delivery_tests/test_behavior_reporting.py
import csv

from cattle_health_app.behavior.reporting import (
    BehaviorObservation,
    write_behavior_reports,
)


def test_reports_separate_uncertain_time_from_eligible_ratios(tmp_path):
    observations = [
        BehaviorObservation(0, 0.0, 7, 2, "grazing", "采食", 0.9, True, "v1"),
        BehaviorObservation(10, 1.0, 7, 2, "grazing", "采食", 0.8, True, "v1"),
        BehaviorObservation(20, 2.0, 7, 1, "uncertain", "无法确定", 0.3, False, "v1"),
    ]
    timeline, summary, rows = write_behavior_reports(observations, tmp_path, "clip")
    assert timeline.name == "clip_behavior.csv"
    assert summary.name == "clip_behavior_summary.csv"
    assert rows == [{
        "track_id": 7,
        "behavior_name": "grazing",
        "behavior_display_name": "采食",
        "duration_seconds": 2.0,
        "eligible_ratio": 1.0,
        "uncertain_duration_seconds": 1.0,
        "model_version": "v1",
    }]
    with timeline.open(encoding="utf-8-sig", newline="") as source:
        assert len(list(csv.DictReader(source))) == 3
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_behavior_reporting.py -q
```

Expected: import fails because `reporting.py` is absent.

- [ ] **Step 3: Implement deterministic duration aggregation**

Create `BehaviorObservation` as a frozen dataclass with the exact positional fields used by the test. Implement `write_behavior_reports(observations, output_dir, source_stem)` so it:

1. Sorts observations by `(track_id, timestamp_seconds, frame_index)`.
2. Uses the positive difference to the next observation for the same track as each row's duration.
3. Uses the most recent positive interval for the final observation; uses `0.0` when a track has only one observation.
4. Writes every observation to `{source_stem}_behavior.csv` using the design-specified columns.
5. Groups eligible durations by `(track_id, behavior_name, display_name, model_version)`.
6. Sums ineligible duration separately per track.
7. Divides each eligible behavior duration by the total eligible duration for that track; uses `0.0` if the denominator is zero.
8. Writes `{source_stem}_behavior_summary.csv` and returns both paths plus JSON-safe summary dictionaries.

Use `csv.DictWriter`, `encoding="utf-8-sig"`, `newline=""`, and round durations/ratios to six decimal places.

- [ ] **Step 4: Run report tests**

Run:

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_behavior_reporting.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit reporting**

```powershell
git add cattle_health_app/behavior/reporting.py delivery_tests/test_behavior_reporting.py
git commit -m "feat: report per-track behavior durations"
```

## Task 4: Integrate optional behavior inference into tracked video

**Files:**

- Modify: `cattle_health_app/tracking_pipeline.py`
- Modify: `delivery_tests/test_tracking_pipeline.py`
- Create: `delivery_tests/test_behavior_video_e2e.py`

- [ ] **Step 1: Extend serialization tests before production code**

Extend `test_tracking_result_serializes_relative_artifacts` with:

```python
result = TrackingVideoResult(
    video_path=result_dir / "tracked.mp4",
    trajectory_csv=result_dir / "tracks.csv",
    alert_csv=result_dir / "alerts.csv",
    health_summary_csv=result_dir / "health.csv",
    health_report_html=result_dir / "health.html",
    frame_count=90,
    tracked_cattle=5,
    alert_count=2,
    behavior_csv=result_dir / "behavior.csv",
    behavior_summary_csv=result_dir / "behavior_summary.csv",
    behavior_model_status="ready",
    behavior_model_version="test-v1",
    behavior_model_error=None,
    behavior_summary=[{"track_id": 7, "behavior_display_name": "采食"}],
)
assert payload["behavior_csv"] == "job-1/behavior.csv"
assert payload["behavior_model_status"] == "ready"
assert payload["behavior_summary"][0]["track_id"] == 7
```

Add an end-to-end test with a fake OpenCV capture/writer, fake detector result, and deterministic fake behavior runtime. The fake runtime returns a `BehaviorPrediction` for Track ID 7. Assert that `process_tracked_video` creates both behavior CSV paths and preserves the existing five artifacts. Add a second test whose runtime raises `RuntimeError("behavior boom")`; assert the returned tracking result has `behavior_model_status == "failed"`, includes `behavior boom`, and still has a trajectory CSV.

- [ ] **Step 2: Run integration tests and verify field/signature failures**

Run:

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_tracking_pipeline.py delivery_tests/test_behavior_video_e2e.py -q
```

Expected: failures because `TrackingVideoResult` and `process_tracked_video` have no behavior fields/runtime argument.

- [ ] **Step 3: Extend the result contract without breaking old callers**

Append defaulted fields to `TrackingVideoResult`:

```python
behavior_csv: Path | None = None
behavior_summary_csv: Path | None = None
behavior_model_status: str = "unavailable"
behavior_model_version: str | None = None
behavior_model_error: str | None = None
behavior_summary: list[dict] | None = None
```

Update `to_dict()` so optional paths serialize relative to `media_root`, `behavior_summary` becomes `[]` when absent, and all existing keys remain unchanged.

- [ ] **Step 4: Integrate crops, predictions, drawing, and graceful failure**

Add `behavior_runtime=None` to `process_tracked_video`. For each tracked `xywh` box:

1. Convert center-based coordinates to integer corners.
2. Expand both dimensions by 15% and clamp to frame bounds.
3. Pass the copied crop to `behavior_runtime.observe(track_id, crop)`.
4. Convert returned predictions to `BehaviorObservation` with current frame/time.
5. Cache the latest prediction per track and draw `ID {track_id} | {display_name} {confidence:.0%}` with `cv2.putText` on `result.plot()`.
6. Catch the first runtime exception, store its text, set the local runtime to `None`, and continue tracking.

After decoding, call `write_behavior_reports`. When no runtime was provided, set status to `unavailable` and do not invent prediction rows. When the runtime failed, set status to `failed`; otherwise set it to `ready` and use `behavior_runtime.model_version`.

- [ ] **Step 5: Run tracking and behavior integration tests**

Run:

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_tracking_pipeline.py delivery_tests/test_behavior_reporting.py delivery_tests/test_behavior_video_e2e.py -q
```

Expected: all tests pass, including detector-only degradation.

- [ ] **Step 6: Commit video integration**

```powershell
git add cattle_health_app/tracking_pipeline.py delivery_tests/test_tracking_pipeline.py delivery_tests/test_behavior_video_e2e.py
git commit -m "feat: annotate tracked video with behavior"
```

## Task 5: Resolve behavior weights and lazily load the runtime

**Files:**

- Modify: `cattle_health_app/model_registry.py`
- Modify: `cattle_health_app/media_processor.py`
- Modify: `run_api.py`
- Modify: `delivery_tests/test_model_registry.py`

- [ ] **Step 1: Write failing optional-model registry tests**

```python
from cattle_health_app.model_registry import resolve_behavior_model


def test_behavior_model_missing_is_nonfatal(tmp_path):
    artifact = resolve_behavior_model(project_root=tmp_path)
    assert artifact.status == "unavailable"
    assert artifact.path == (tmp_path / "models/behavior/cvb_x3d_v2_best.pt").resolve()
    assert artifact.sha256 is None


def test_behavior_model_is_fingerprinted(tmp_path):
    weight = tmp_path / "behavior.pt"
    weight.write_bytes(b"behavior")
    artifact = resolve_behavior_model(weight, project_root=tmp_path)
    assert artifact.status == "ready"
    assert len(artifact.sha256) == 64
```

- [ ] **Step 2: Run registry tests and verify failure**

Run:

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_model_registry.py -q
```

Expected: import fails because `resolve_behavior_model` is absent.

- [ ] **Step 3: Implement optional behavior artifact resolution**

Add this contract to `model_registry.py`:

```python
@dataclass(frozen=True)
class BehaviorModelArtifact:
    name: str
    path: Path
    sha256: str | None
    status: str
    version: str | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["path"] = str(self.path)
        return payload
```

Implement `resolve_behavior_model(explicit_path=None, project_root=None)` with precedence: explicit path, `AGRINEBULA_BEHAVIOR_MODEL`, then `models/behavior/cvb_x3d_v2_best.pt`. Missing files return `unavailable`; regular files return `ready` plus SHA-256. Do not load Torch in the registry.

- [ ] **Step 4: Add lazy runtime loading and CPU fallback**

Extend `LocalMediaProcessor.__init__` with `behavior_model_path=None`. Store the behavior artifact and `_behavior_runtime`. Add `_load_behavior_runtime()` that:

1. Returns `None` for an unavailable artifact.
2. Chooses `cuda` when `torch.cuda.is_available()`, otherwise `cpu`.
3. Calls `load_behavior_checkpoint`.
4. On CUDA runtime failure, retries once on CPU.
5. Constructs `BehaviorRuntime(loaded.model, loaded.metadata.model_version, device)`.
6. On final failure, replaces the artifact with status `failed` and returns `None`.

Pass the returned runtime to `process_tracked_video` using a keyword argument. In `run_api.py`, construct the processor with default behavior path `PROJECT_ROOT / "models" / "behavior" / "cvb_x3d_v2_best.pt"`.

- [ ] **Step 5: Run model registry and processor regression tests**

Run:

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_model_registry.py delivery_tests/test_delivery_reliability.py delivery_tests/test_video_jobs.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit model wiring**

```powershell
git add cattle_health_app/model_registry.py cattle_health_app/media_processor.py run_api.py delivery_tests/test_model_registry.py delivery_tests/test_delivery_reliability.py delivery_tests/test_video_jobs.py
git commit -m "feat: load optional behavior model"
```

## Task 6: Expose behavior status through the API and job JSON

**Files:**

- Modify: `cattle_health_app/api.py`
- Modify: `delivery_tests/test_delivery_api.py`
- Modify: `delivery_tests/test_video_jobs.py`

- [ ] **Step 1: Write failing API and job assertions**

In the delivery API fixture, construct:

```python
behavior_artifact = BehaviorModelArtifact(
    name="cvb-x3d-behavior",
    path=tmp_path / "behavior.pt",
    sha256="a" * 64,
    status="ready",
    version="cvb-x3d-v1",
)
```

Pass it as `behavior_artifact=behavior_artifact` to `create_app`, then assert:

```python
payload = client.get("/api/models").json()
assert payload["behavior"]["status"] == "ready"
assert payload["behavior"]["version"] == "cvb-x3d-v1"
```

Extend the fake completed job result with both behavior paths, status, version, error, and a one-row summary. Assert the repository round-trip preserves each value.

- [ ] **Step 2: Run API/job tests and verify signature failures**

Run:

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_delivery_api.py delivery_tests/test_video_jobs.py -q
```

Expected: `create_app` rejects `behavior_artifact`, or `/api/models` omits `behavior`.

- [ ] **Step 3: Extend the API factory and model response**

Add `behavior_artifact=None` to `create_app`. Resolve it from `media_processor.behavior_artifact` when present; otherwise call `resolve_behavior_model()`. Return:

```python
@app.get("/api/models")
def models():
    return {
        "detector": detector_artifact.to_dict(),
        "behavior": behavior_artifact.to_dict(),
    }
```

The existing `VideoJobRecord.result` JSON column already stores arbitrary dictionaries, so do not add database columns. Confirm `TrackingVideoResult.to_dict()` is the only job-result serialization boundary.

- [ ] **Step 4: Run API/job tests**

Run:

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_delivery_api.py delivery_tests/test_video_jobs.py tests/test_web_api.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit API integration**

```powershell
git add cattle_health_app/api.py delivery_tests/test_delivery_api.py delivery_tests/test_video_jobs.py
git commit -m "feat: expose behavior model status"
```

## Task 7: Display behavior results in React

**Files:**

- Modify: `web/src/api.ts`
- Modify: `web/src/RecognitionStudio.tsx`
- Modify: `web/src/workspace-interactions.css`
- Modify: `web/src/App.test.tsx`

- [ ] **Step 1: Add a completed-job fixture and failing UI assertions**

Extend the mocked completed video job in `App.test.tsx` with:

```typescript
behavior_csv: "job-1/cattle_behavior.csv",
behavior_summary_csv: "job-1/cattle_behavior_summary.csv",
behavior_model_status: "ready",
behavior_model_version: "cvb-x3d-v1",
behavior_model_error: null,
behavior_summary: [
  {
    track_id: 7,
    behavior_name: "grazing",
    behavior_display_name: "采食",
    duration_seconds: 12.5,
    eligible_ratio: 0.625,
    uncertain_duration_seconds: 2.0,
    model_version: "cvb-x3d-v1",
  },
],
```

After uploading a video and waiting for completion, assert:

```typescript
expect(await screen.findByText("研究演示模型")).toBeInTheDocument();
expect(screen.getByText("视频内 ID 7")).toBeInTheDocument();
expect(screen.getByText("采食")).toBeInTheDocument();
expect(screen.getByText("12.5 秒")).toBeInTheDocument();
expect(screen.getByText("62.5%")).toBeInTheDocument();
expect(screen.getByRole("link", { name: "行为时间线 CSV" })).toBeInTheDocument();
```

Add a second test with `behavior_model_status: "unavailable"` and assert “行为模型未加载” and the result video are both visible.

- [ ] **Step 2: Run the React test and verify type/UI failures**

Run from `web`:

```powershell
npm test -- --run src/App.test.tsx
```

Expected: TypeScript fixture or element-query failures for missing behavior fields/UI.

- [ ] **Step 3: Extend exact TypeScript result types**

Add:

```typescript
export type BehaviorSummaryRow = {
  track_id: number;
  behavior_name: string;
  behavior_display_name: string;
  duration_seconds: number;
  eligible_ratio: number;
  uncertain_duration_seconds: number;
  model_version: string;
};
```

Extend `TrackingResult` with nullable behavior paths/version/error, status union `"ready" | "unavailable" | "failed"`, and `behavior_summary: BehaviorSummaryRow[]`.

- [ ] **Step 4: Render behavior status, summary, and downloads**

In `RecognitionStudio`, below existing result artifacts:

1. When status is `ready`, render a section headed “行为识别（研究演示模型）”.
2. Show the model version.
3. Group rows by `track_id` and label groups as `视频内 ID {id}`.
4. Display behavior name, `duration_seconds.toFixed(1) 秒`, and `(eligible_ratio * 100).toFixed(1)%`.
5. Display the maximum `uncertain_duration_seconds` once per track.
6. Add “行为时间线 CSV” and “行为汇总 CSV” links using `resultMediaUrl`.
7. For `unavailable`, render “行为模型未加载，检测、追踪和规则健康分析仍可用。”
8. For `failed`, render “行为识别运行失败，其他结果已保留。” and the escaped error text.

Add responsive styles under `.behavior-result`, `.behavior-track`, `.behavior-table`, and `.behavior-unavailable`; preserve visible focus styling and horizontal overflow on narrow screens.

- [ ] **Step 5: Run React tests and production build**

Run from `web`:

```powershell
npm test -- --run
npm run build
```

Expected: all tests pass and Vite production build succeeds.

- [ ] **Step 6: Commit the UI**

```powershell
git add web/src/api.ts web/src/RecognitionStudio.tsx web/src/workspace-interactions.css web/src/App.test.tsx
git commit -m "feat: show per-track behavior results"
```

## Task 8: Install and verify the real checkpoint

**Files:**

- Generate: `models/behavior/cvb_x3d_v2_best.pt`
- Modify: `.gitignore`
- Modify: `README.md`
- Modify: `README_DELIVERY.md`

- [ ] **Step 1: Verify source and target paths before copying**

Run:

```powershell
Get-Item -LiteralPath 'F:\new大创\outputs\cvb_x3d_v2\best.pt' | Select-Object FullName,Length,LastWriteTime
Test-Path -LiteralPath 'F:\new大创\models\behavior\cvb_x3d_v2_best.pt'
```

Expected: source exists and is approximately 12 MB; record whether the target already exists. If the target exists, compare hashes and do not overwrite a different file without explicit user approval.

- [ ] **Step 2: Install a non-destructive copy and fingerprint both files**

Create `models/behavior` if absent. Copy the source to a temporary filename in that directory, verify equal SHA-256 values, then atomically rename the temporary file to `cvb_x3d_v2_best.pt`. Keep `outputs/cvb_x3d_v2/best.pt` unchanged.

Run:

```powershell
Get-FileHash -Algorithm SHA256 'F:\new大创\outputs\cvb_x3d_v2\best.pt'
Get-FileHash -Algorithm SHA256 'F:\new大创\models\behavior\cvb_x3d_v2_best.pt'
```

Expected: hashes are identical.

- [ ] **Step 3: Load the installed checkpoint on CPU**

Run:

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -c "from cattle_health_app.behavior.model import load_behavior_checkpoint; x=load_behavior_checkpoint(r'models\behavior\cvb_x3d_v2_best.pt','cpu'); print(x.metadata.model_version, x.metadata.input_frames, x.metadata.input_size, len(x.metadata.labels))"
```

Expected: prints a nonempty version followed by `16 224 12`.

- [ ] **Step 4: Document the exact research-model evidence**

Add `models/behavior/*.pt` to `.gitignore`. Update both READMEs with:

- Installed filename and exact SHA-256 from Step 2.
- Accuracy `0.8342201644668648` and Macro-F1 `0.2188597785907576`.
- Explanation that class imbalance makes accuracy misleading.
- Startup behavior when the model is missing or fails.
- Behavior CSV names and UI location.
- “研究演示结果，仅用于风险筛查辅助，不是疾病诊断。”

Do not claim an accuracy target or production diagnostic readiness.

- [ ] **Step 5: Commit metadata and documentation, not the weight**

```powershell
git add .gitignore README.md README_DELIVERY.md
git commit -m "docs: record behavior model delivery"
```

## Task 9: Run complete regression and real-video acceptance

**Files:**

- Modify only if an acceptance defect is found: files owned by Tasks 1-8

- [ ] **Step 1: Run all Python tests**

Run:

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest -q -p no:cacheprovider
```

Expected: all tests pass with no new warnings caused by behavior integration.

- [ ] **Step 2: Run frontend regression and build**

Run from `web`:

```powershell
npm test -- --run --reporter=dot
npm run build
```

Expected: all tests pass and production build succeeds.

- [ ] **Step 3: Run delivery preflight**

Run:

```powershell
$env:AGRINEBULA_PYTHON = 'F:\deepl\anaconda1\envs\pytorch\python.exe'
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_delivery.ps1 -CheckOnly
```

Expected: `Delivery preflight passed.` and both detector and application files resolve.

- [ ] **Step 4: Verify a real uploaded MP4**

Start the project with `start_delivery.ps1`. Upload a short cattle MP4 through the existing Web UI and wait for completion. Confirm:

- Result video is playable or downloadable.
- Overlay includes Track ID, Chinese behavior label, and confidence after warm-up.
- Both behavior CSV links download valid UTF-8 CSV files.
- UI shows research-model notice, model version, per-track durations, eligible ratios, and uncertain time.
- Existing trajectory, health alert, health summary, and HTML report remain available.
- `/api/models` returns the installed behavior hash and ready status.

- [ ] **Step 5: Verify detector-only degradation**

Stop the service. Set `AGRINEBULA_BEHAVIOR_MODEL` to a nonexistent explicit test path, restart, and upload the same short MP4. Confirm the job completes, all original artifacts remain available, `/api/models` reports behavior unavailable, and the UI displays “行为模型未加载”. Remove the temporary environment override after the test; do not move or delete the installed weight.

- [ ] **Step 6: Record final evidence and commit only necessary fixes**

Run:

```powershell
git status --short
git log -10 --oneline
```

Expected: no unintended tracked changes; user-owned `.idea`, `=ro`, `cloud_pack`, and `cloud_upload` remain untouched. If acceptance required code fixes, rerun the smallest failing test first, then Steps 1-3, and commit only the related files with a scoped `fix:` message.

## Plan self-review

- Every design requirement maps to Tasks 1-9.
- Retraining, new health alerts, camera input, permanent identity, and disease diagnosis remain out of scope.
- Behavior model failure is non-blocking at registry, load, inference, reporting, API, and UI boundaries.
- Type names and JSON keys are consistent from `TrackingVideoResult` through API and TypeScript.
- The real checkpoint is copied, fingerprinted, ignored by Git, and never removed from `outputs`.
- Each production change begins with a failing test and ends with focused verification and a scoped commit.

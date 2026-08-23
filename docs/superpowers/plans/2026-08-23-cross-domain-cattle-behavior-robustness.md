# Cross-Domain Cattle Behavior Robustness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a provenance-safe, reproducible CVB-to-CBVD-5 cross-domain cattle behavior benchmark with frozen calibration, quality-aware selective prediction, controlled video degradations, paper-ready reports, and a defense-facing results view.

**Architecture:** Keep external data governance, acquisition, dataset parsing, clip construction, quality measurement, experiment execution, and reporting in separate modules under `cattle_health_app/behavior`. All large media stays below `data/external` and is ignored by Git; committed manifests preserve source URLs, licenses, hashes, transformations, mappings, exclusions, and split groups. The existing X3D checkpoint and calibration policy are immutable inputs to a test-only external benchmark; any later few-shot adaptation uses a new group-isolated protocol.

**Tech Stack:** Python 3.8, dataclasses, pathlib, csv/json, requests, OpenCV, NumPy, pandas, PyTorch, scikit-learn, matplotlib, pytest, FastAPI, React, TypeScript, Vitest.

---

## File map

Create focused modules:

- `cattle_health_app/behavior/external_registry.py`: typed dataset registry and license-state validation.
- `cattle_health_app/behavior/external_download.py`: budgeted downloads, hashing, safe ZIP extraction, and append-only operation records.
- `cattle_health_app/behavior/cbvd5.py`: CBVD-5 annotation parsing and strict/extended label mapping.
- `cattle_health_app/behavior/external_clips.py`: source-group IDs, deterministic selection, clip provenance, and leakage checks.
- `cattle_health_app/behavior/quality.py`: image/video/track quality measurements and quality-gate scoring.
- `cattle_health_app/behavior/degradations.py`: deterministic controlled corruptions.
- `cattle_health_app/behavior/cross_domain_experiment.py`: frozen model protocol, inference records, metrics, and ablations.
- `cattle_health_app/behavior/cross_domain_reporting.py`: CSV/JSON/Markdown/PNG outputs.
- `scripts/prepare_external_behavior_data.py`: registry, inspection, acquisition, extraction, and manifest CLI.
- `scripts/run_cross_domain_behavior_experiment.py`: experiment and report CLI.
- `data/external/registry.json`: machine-readable official-source registry.
- `docs/data/2026-08-23-public-cattle-video-data-record.md`: user-facing dataset and operations ledger.
- `docs/experiments/2026-08-23-cross-domain-behavior-results.md`: final scientific result and claim boundaries.

Tests mirror each module in `delivery_tests/`. Frontend/API changes occur only after result JSON exists.

## Execution order and change log

Execute tasks in this dependency order: `1 -> 2 -> 10 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9 -> 11 -> 12 -> 13 -> 14`.

- `2026-08-23`: Moved the metadata/license inspection gate (Task 10) ahead of the CBVD-5 parser (Task 3). The original numeric order could have encouraged implementing an annotation adapter from assumptions. The revised order verifies the official file list, license, and a small official annotation/metadata sample before the parser contract is finalized. The `5 GiB` cap, frozen-test protocol, label-mapping boundaries, and VLM deferral are unchanged.

### Task 1: External dataset registry and provenance contract

**Files:**
- Create: `delivery_tests/test_external_dataset_registry.py`
- Create: `cattle_health_app/behavior/external_registry.py`
- Create: `data/external/registry.json`
- Create: `docs/data/2026-08-23-public-cattle-video-data-record.md`
- Modify: `.gitignore`

- [ ] **Step 1: Write failing registry tests**

Test a valid record, reject an unknown license state, reject a relative/escaping storage root, and require official URL, access URL, intended use, download budget, and status.

```python
def test_registry_loads_cbvd5_with_project_relative_storage(tmp_path):
    registry = load_registry(FIXTURE, project_root=tmp_path)
    cbvd5 = registry.require("cbvd5")
    assert cbvd5.license_status == "verify_before_download"
    assert cbvd5.storage_root == tmp_path / "data" / "external" / "cbvd5"


def test_registry_rejects_storage_outside_project(tmp_path):
    with pytest.raises(RegistryError, match="inside project_root"):
        load_registry(registry_file(tmp_path, storage_root="../outside"), tmp_path)
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest delivery_tests/test_external_dataset_registry.py -q`

Expected: collection fails because `external_registry` does not exist.

- [ ] **Step 3: Implement typed registry validation**

Define immutable `DatasetRecord` and `DatasetRegistry`. Allowed license states are `verified`, `verify_before_download`, `blocked_license`, and `not_used`. Resolve storage paths against an explicit project root and reject any path whose resolved form is outside it.

```python
@dataclass(frozen=True)
class DatasetRecord:
    dataset_id: str
    name: str
    version: str
    official_url: str
    access_url: str
    license_name: str
    license_url: str
    license_status: str
    intended_use: str
    storage_root: Path
    max_download_bytes: int
```

- [ ] **Step 4: Add initial registry and ledger**

Register `cvb`, `cbvd5`, `mmcows`, and `cattleeyeview`. CBVD-5 starts as `verify_before_download`; MmCows records `CC-BY-NC-SA-4.0`; CattleEyeView is `not_used`. The ledger states that no external files have been downloaded yet and includes headings for operations, hashes, exclusions, and plan changes.

- [ ] **Step 5: Ignore only external large-data directories**

Add rules for archives, raw media, derived frames/clips, and experiment caches. Negate `registry.json`, manifests, `.gitkeep`, result summaries, and documentation so provenance stays tracked.

- [ ] **Step 6: Run focused tests and commit**

Run: `python -m pytest delivery_tests/test_external_dataset_registry.py -q`

Expected: all tests pass.

Commit: `feat: add external cattle dataset registry`

### Task 2: Budgeted acquisition, hashing, and safe extraction

**Files:**
- Create: `delivery_tests/test_external_dataset_download.py`
- Create: `cattle_health_app/behavior/external_download.py`

- [ ] **Step 1: Write failing acquisition tests**

Cover: blocked unverified license, expected-size budget rejection before network access, streamed budget overflow, idempotent reuse after SHA-256 match, corrupt hash rejection, ZIP path traversal rejection, and append-only JSONL operation records.

```python
def test_download_refuses_unverified_license(tmp_path):
    with pytest.raises(DownloadBlocked, match="license"):
        acquire_file(record(status="verify_before_download"), file_spec(), tmp_path)


def test_safe_extract_rejects_zip_slip(tmp_path):
    archive = malicious_zip(tmp_path, "../escape.mp4")
    with pytest.raises(UnsafeArchive, match="outside extraction root"):
        safe_extract_zip(archive, tmp_path / "raw")
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest delivery_tests/test_external_dataset_download.py -q`

Expected: import failure for the missing module.

- [ ] **Step 3: Implement download primitives**

Add `RemoteFileSpec`, `AcquisitionResult`, `sha256_file`, `acquire_file`, `safe_extract_zip`, and `append_operation`. Accept an injected stream opener so tests never use the internet. Write to a `.part` file, enforce the cumulative byte limit while streaming, verify hash when supplied, then atomically rename inside the dataset archive directory.

- [ ] **Step 4: Verify GREEN and commit**

Run: `python -m pytest delivery_tests/test_external_dataset_download.py -q`

Expected: all tests pass without network access.

Commit: `feat: add provenance-safe external data acquisition`

### Task 3: CBVD-5 annotation parsing and transparent label mapping

**Files:**
- Create: `delivery_tests/test_cbvd5_dataset.py`
- Create: `cattle_health_app/behavior/cbvd5.py`

- [ ] **Step 1: Write failing parser and mapping tests**

Use tiny committed CSV fixtures constructed in the test. Verify source labels are retained, combined posture/state labels map correctly, approximate mappings are excluded from strict mode, conflicts are rejected, and malformed times/boxes produce explicit exclusion records.

```python
@pytest.mark.parametrize(
    "source,expected",
    [
        (("foraging",), "grazing"),
        (("drinking",), "drinking"),
        (("rumination", "standing"), "ruminating-standing"),
        (("rumination", "lying"), "ruminating-lying"),
    ],
)
def test_strict_mapping(source, expected):
    mapped = map_cbvd5_labels(source, tier="strict")
    assert mapped.name == expected
    assert mapped.mapping_tier == "strict"
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest delivery_tests/test_cbvd5_dataset.py -q`

Expected: import failure for `cbvd5`.

- [ ] **Step 3: Implement canonical records and parser adapters**

Define `SourceAnnotation`, `MappedAnnotation`, `ExcludedAnnotation`, and an adapter matching the official annotation/metadata sample verified in Task 10. Keep input-specific column names inside the adapter and expose one canonical iterator. Implement both `strict` and `extended` mapping tables without changing `cvb_labels.py`.

- [ ] **Step 4: Verify GREEN and commit**

Run: `python -m pytest delivery_tests/test_cbvd5_dataset.py -q`

Expected: all tests pass.

Commit: `feat: parse and align CBVD-5 behavior labels`

### Task 4: Source groups, deterministic sampling, and clip manifests

**Files:**
- Create: `delivery_tests/test_external_behavior_clips.py`
- Create: `cattle_health_app/behavior/external_clips.py`

- [ ] **Step 1: Write failing provenance and leakage tests**

Verify stable IDs, same source video/camera/time block produces the same group, deterministic class caps, no group crosses requested splits, and every derived clip has a source path, start/end time, crop track, mapping tier, transformation list, and output hash.

```python
def test_split_groups_never_cross_boundaries(records):
    split = assign_groups(records, seed=20260823, ratios=(0.0, 0.0, 1.0))
    owners = {}
    for item in split:
        assert owners.setdefault(item.source_group_id, item.split) == item.split
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest delivery_tests/test_external_behavior_clips.py -q`

- [ ] **Step 3: Implement manifest creation**

Use SHA-256 identifiers derived from source dataset/version/video/camera/time/track. Default external zero-shot split is `test`; adaptation mode must receive explicit group ratios. Call existing frame/crop utilities where compatible, but write a separate manifest containing source provenance rather than changing the CVB index format.

- [ ] **Step 4: Verify GREEN and commit**

Run: `python -m pytest delivery_tests/test_external_behavior_clips.py -q`

Commit: `feat: build leakage-safe external clip manifests`

### Task 5: Quality and temporal-consistency evidence

**Files:**
- Create: `delivery_tests/test_behavior_video_quality.py`
- Create: `cattle_health_app/behavior/quality.py`

- [ ] **Step 1: Write failing feature tests**

Generate synthetic images and tracks in memory. Assert black frames have high dark ratio, constant frames have lower Laplacian variance than checkerboards, boundary-touching boxes have positive truncation, missing frame indices reduce continuity, and unstable probability sequences have lower agreement.

```python
def test_blur_score_separates_flat_and_textured_frames():
    flat = np.full((64, 64, 3), 128, np.uint8)
    textured = checkerboard(64)
    assert frame_quality(flat).laplacian_variance < frame_quality(textured).laplacian_variance
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest delivery_tests/test_behavior_video_quality.py -q`

- [ ] **Step 3: Implement deterministic quality records**

Define `FrameQuality`, `TrackQuality`, and `WindowQuality`. Use normalized, resolution-independent values where possible. Implement no learned threshold here; this module only measures evidence.

- [ ] **Step 4: Verify GREEN and commit**

Run: `python -m pytest delivery_tests/test_behavior_video_quality.py -q`

Commit: `feat: measure behavior video quality evidence`

### Task 6: Frozen cross-domain protocol and quality-aware gate

**Files:**
- Create: `delivery_tests/test_cross_domain_behavior_experiment.py`
- Create: `cattle_health_app/behavior/cross_domain_experiment.py`
- Modify: `cattle_health_app/behavior/uncertainty.py`

- [ ] **Step 1: Write failing protocol tests**

Use deterministic logits and quality rows. Verify external labels cannot be supplied to gate fitting, checkpoint/calibration hashes must match, strict and extended rows remain separate, abstention metrics match hand calculations, and a fitted gate serializes its training domain as `cvb_validation`.

```python
def test_gate_fit_rejects_external_training_domain():
    with pytest.raises(ProtocolViolation, match="cvb_validation"):
        fit_quality_gate(rows, training_domain="cbvd5_test")


def test_frozen_protocol_rejects_calibration_hash_mismatch(tmp_path):
    with pytest.raises(ProtocolViolation, match="checkpoint_sha256"):
        load_frozen_protocol(checkpoint, incompatible_calibration(tmp_path))
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest delivery_tests/test_cross_domain_behavior_experiment.py -q`

- [ ] **Step 3: Implement experiment records and metric variants**

Reuse existing calibration and metric functions. Add `CrossDomainProtocol`, `ExternalPrediction`, `QualityGate`, and `evaluate_variants`. Variants are exactly `uncalibrated`, `calibrated`, `calibrated_fixed_rejection`, and `calibrated_quality_rejection`. Preserve raw 12-class probabilities for audit.

- [ ] **Step 4: Implement a simple interpretable gate**

Fit standardization and logistic regression only on CVB validation rows, with target `raw prediction is correct and health-eligible`. Choose its acceptance threshold using the existing minimum eligible coverage constraint and deterministic tie-breaking. Store feature order, means, scales, coefficients, intercept, threshold, seed, training domain, checkpoint hash, and input manifest hash.

- [ ] **Step 5: Verify GREEN and commit**

Run: `python -m pytest delivery_tests/test_cross_domain_behavior_experiment.py delivery_tests/test_behavior_uncertainty.py -q`

Commit: `feat: evaluate quality-aware selective behavior recognition`

### Task 7: Deterministic controlled degradations

**Files:**
- Create: `delivery_tests/test_behavior_degradations.py`
- Create: `cattle_health_app/behavior/degradations.py`

- [ ] **Step 1: Write failing degradation tests**

Verify level zero returns identical content, equal seeds return identical occlusions/frame drops, increasing blur levels do not increase Laplacian variance, dimensions and frame count contracts are explicit, and input arrays are not modified.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest delivery_tests/test_behavior_degradations.py -q`

- [ ] **Step 3: Implement six named degradations**

Implement `blur`, `low_light`, `occlusion`, `downsample`, `frame_drop`, and `compression`. Each returns frames plus a serializable `TransformationRecord` containing name, level, parameters, and seed.

- [ ] **Step 4: Verify GREEN and commit**

Run: `python -m pytest delivery_tests/test_behavior_degradations.py -q`

Commit: `feat: add reproducible behavior video stress tests`

### Task 8: Reproducible preparation and experiment CLIs

**Files:**
- Create: `delivery_tests/test_external_behavior_cli.py`
- Create: `scripts/prepare_external_behavior_data.py`
- Create: `scripts/run_cross_domain_behavior_experiment.py`

- [ ] **Step 1: Write failing CLI tests**

Call `main(argv)` against temporary fixtures. Assert `inspect` performs no download, `acquire` refuses an unverified license, `prepare` writes manifests and exclusions, and `run --dry-run` validates all frozen hashes without loading PyTorch weights.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest delivery_tests/test_external_behavior_cli.py -q`

- [ ] **Step 3: Implement preparation commands**

Support:

```text
prepare_external_behavior_data.py inspect --dataset cbvd5
prepare_external_behavior_data.py acquire --dataset cbvd5 --file video_cut
prepare_external_behavior_data.py prepare --dataset cbvd5 --tier strict
```

`inspect` prints license state, declared/remote size, remaining budget, destination, and planned operations. `acquire` requires `license_status=verified`. `prepare` never downloads implicitly.

- [ ] **Step 4: Implement experiment command**

Support:

```text
run_cross_domain_behavior_experiment.py --manifest <csv> --output <dir> --seed 20260823
run_cross_domain_behavior_experiment.py --manifest <csv> --output <dir> --stress-levels 0,1,2,3
```

Write `protocol.json` before inference and refuse an existing output directory whose protocol differs. Allow `--resume` only when hashes match.

- [ ] **Step 5: Verify GREEN and commit**

Run: `python -m pytest delivery_tests/test_external_behavior_cli.py -q`

Commit: `feat: add external behavior experiment commands`

### Task 9: Paper-ready reporting

**Files:**
- Create: `delivery_tests/test_cross_domain_behavior_reporting.py`
- Create: `cattle_health_app/behavior/cross_domain_reporting.py`
- Create: `docs/experiments/2026-08-23-cross-domain-behavior-results.md`

- [ ] **Step 1: Write failing report tests**

Use a five-row fixture and assert stable CSV column order, separate strict/extended tables, correct best-variant selection without test-time tuning, risk-coverage points, degradation grouping, escaped Markdown, and valid PNG files.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest delivery_tests/test_cross_domain_behavior_reporting.py -q`

- [ ] **Step 3: Implement structured outputs**

Generate `predictions.csv`, `metrics.json`, `protocol_comparison.csv`, `per_class_metrics.csv`, `risk_coverage.csv`, `stress_metrics.csv`, `confusion_matrix.png`, `risk_coverage.png`, `stress_curves.png`, and `summary.md`. The report must label unsupported claims and show external sample counts beside every metric.

- [ ] **Step 4: Add result-document template with honest states**

The committed document supports `not_run`, `blocked`, and `complete`. Before real execution it says no external result exists; after execution it records hashes, commands, tables, limitations, and whether the quality gate improved risk at comparable coverage.

- [ ] **Step 5: Verify GREEN and commit**

Run: `python -m pytest delivery_tests/test_cross_domain_behavior_reporting.py -q`

Commit: `feat: report cross-domain behavior robustness results`

### Task 10: Inspect official data metadata and update the plan before parser implementation or media download

**Files:**
- Modify: `data/external/registry.json`
- Modify: `docs/data/2026-08-23-public-cattle-video-data-record.md`
- Modify if facts changed: `docs/superpowers/specs/2026-08-23-cross-domain-cattle-behavior-robustness-design.md`
- Modify if facts changed: `docs/superpowers/plans/2026-08-23-cross-domain-cattle-behavior-robustness.md`

- [ ] **Step 1: Run metadata-only inspection**

Use the official Kaggle API/CLI or public dataset page to list files, sizes, versions, and license without downloading media. After the license gate passes, acquire only the smallest official annotation/metadata file needed to verify the parser schema; record its size and hash against the same `5 GiB` budget. Do not store credentials in the repository.

- [ ] **Step 2: Apply the acquisition gate**

Proceed with CBVD-5 only if the dataset license permits this non-commercial research use, required video and annotation files can be acquired through the official mechanism, and planned bytes do not exceed `5 GiB`. Otherwise record `blocked_license`, `blocked_access`, or `blocked_budget` and inspect MmCows under the same rules.

- [ ] **Step 3: Record any plan change before continuing**

Add a dated change entry with old assumption, observed fact, impact, chosen fallback, and unchanged scientific constraints. Update the active Goal/plan status in the same turn.

- [ ] **Step 4: Commit the verified metadata**

Commit: `docs: verify external cattle dataset acquisition metadata`

### Task 11: Acquire, prepare, and audit the real external subset

**Files:**
- Create ignored media under: `data/external/<dataset>/archives/`
- Create ignored extracted data under: `data/external/<dataset>/raw/`
- Create tracked manifests under: `data/external/<dataset>/manifests/`
- Modify: `docs/data/2026-08-23-public-cattle-video-data-record.md`

- [ ] **Step 1: Run `inspect` and save the console summary in the ledger**

- [ ] **Step 2: Acquire only approved files**

Stop automatically at the byte budget. Record source URL, ETag/version when exposed, local size, and SHA-256.

- [ ] **Step 3: Extract and inventory non-destructively**

Keep archives. Write file inventory before parsing. Never rewrite original media.

- [ ] **Step 4: Generate strict and extended manifests**

Write `source_videos.csv`, `evaluation_clips_strict.csv`, `evaluation_clips_extended.csv`, `excluded_samples.csv`, and `manifest_summary.json`.

- [ ] **Step 5: Audit samples visually and structurally**

Inspect at least 10 deterministic samples per mapped class when available. Record annotation/video mismatch, crop quality, behavior visibility, and exclusions. Do not relabel ambiguous samples by model prediction.

- [ ] **Step 6: Validate and commit manifests/ledger**

Run all focused data tests and a manifest validation command. Commit only manifests, summaries, hashes, and documentation.

Commit: `data: register external cattle behavior benchmark subset`

### Task 12: Run frozen baseline, quality gate, and stress experiments

**Files:**
- Create ignored caches under: `outputs/cross_domain/cvb_to_cbvd5/`
- Track compact summaries/figures according to repository policy
- Modify: `docs/experiments/2026-08-23-cross-domain-behavior-results.md`
- Modify: `docs/data/2026-08-23-public-cattle-video-data-record.md`

- [ ] **Step 1: Run dry-run protocol validation**

Verify checkpoint SHA-256, calibration/checkpoint binding, manifest hash, class mapping, output location, CUDA/CPU selection, and available disk space.

- [ ] **Step 2: Run zero-shot strict and extended baselines once**

Do not change thresholds after seeing results. Preserve per-sample logits and quality evidence.

- [ ] **Step 3: Fit the quality gate only on CVB validation data**

Save the gate artifact and its training-manifest hash. Then apply it to the already frozen external predictions without refitting.

- [ ] **Step 4: Run controlled degradations**

Use the same selected source clips and fixed seed for all variants and levels.

- [ ] **Step 5: Generate reports and check numerical invariants**

Confirm counts reconcile across prediction/metric files, coverage is within `[0,1]`, confusion-matrix totals match eligible samples, and calibration does not change argmax predictions.

- [ ] **Step 6: Evaluate the few-shot Go/No-Go gate**

Start a separate adaptation plan only when strict zero-shot Macro-F1 is below `0.30` and every included class has at least four independent source groups after reserving a final test group. Otherwise write the exact skip reason. No adaptation code is added inside this plan.

- [ ] **Step 7: Commit compact results**

Commit: `exp: evaluate cross-domain cattle behavior robustness`

### Task 13: Defense-facing API and results view

**Files:**
- Create: `delivery_tests/test_cross_domain_results_api.py`
- Modify: `cattle_health_app/api.py`
- Modify: `web/src/api.ts`
- Create: `web/src/CrossDomainResults.test.tsx`
- Create: `web/src/CrossDomainResults.tsx`
- Modify: `web/src/RecognitionStudio.tsx`
- Modify: `web/src/styles.css`

- [ ] **Step 1: Write failing API contract tests**

Assert the endpoint returns `not_run` when no summary exists, validates the committed schema when complete, and never serves arbitrary paths from result JSON.

- [ ] **Step 2: Run API test and verify RED**

Run: `python -m pytest delivery_tests/test_cross_domain_results_api.py -q`

- [ ] **Step 3: Implement read-only summary endpoint**

Expose only status, dataset/version, sample count, frozen model hash prefix, variant metrics, limitations, and application-relative figure URLs from the fixed output root.

- [ ] **Step 4: Write failing React tests**

Assert `not_run`, `blocked`, and `complete` states; strict/extended labels; quality rejection reason; research-only disclaimer; and figure alternative text.

- [ ] **Step 5: Run frontend test and verify RED**

Run: `npm test -- --run src/CrossDomainResults.test.tsx`

- [ ] **Step 6: Implement the minimal results component**

Display dataset provenance, domain-shift comparison, coverage/risk, quality evidence, and limitations. Do not add live VLM controls or claims of disease diagnosis.

- [ ] **Step 7: Verify GREEN and commit**

Run API and frontend focused tests.

Commit: `feat: present cross-domain robustness evidence`

### Task 14: Full verification, review, and delivery

**Files:**
- Modify: `README_BEHAVIOR_DATA.md`
- Modify: `docs/data/2026-08-23-public-cattle-video-data-record.md`
- Modify: `docs/experiments/2026-08-23-cross-domain-behavior-results.md`

- [ ] **Step 1: Run all Python tests**

Run: `python -m pytest -q`

Expected: no failures; environment-dependent tests may only skip for documented existing reasons.

- [ ] **Step 2: Run frontend tests and build**

Run from `web`: `npm test -- --run`

Run from `web`: `npm run build`

Expected: all tests pass and Vite production build succeeds.

- [ ] **Step 3: Run delivery preflight and one small end-to-end experiment**

Verify the API, existing upload pipeline, behavior result rendering, external result endpoint, and downloadable experiment artifacts.

- [ ] **Step 4: Perform code and scientific-claim review**

Check path containment, archive extraction, untrusted CSV/JSON handling, hash enforcement, leakage, test-time threshold tuning, mapping boundaries, metric denominators, and claims unsupported by sample count.

- [ ] **Step 5: Verify repository scope and provenance**

Confirm every modified file is below `F:\new大创`, no credentials or large raw media are tracked, the ledger matches actual hashes/paths, and the Git worktree is clean except intended changes.

- [ ] **Step 6: Commit final documentation**

Commit: `docs: finalize cross-domain behavior experiment delivery`

## Deferred final roadmap: VLM, multimodality, and embodied intelligence

This roadmap is deliberately outside the implementation tasks above. After Tasks 1–14 are complete, create a separate reviewed spec for: selective VLM review of rejected clips; video temporal grounding and evidence explanations; RGB/thermal/environment/history fusion; and eventually human-approved PTZ camera or inspection-robot actions. No VLM dependency, checkpoint, API call, UI control, or embodied-device action is added by this plan.

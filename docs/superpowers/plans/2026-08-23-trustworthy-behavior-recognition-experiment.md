# Trustworthy Behavior Recognition Experiment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run a leakage-safe temperature-calibration and selective-rejection experiment for the existing CVB X3D checkpoint.

**Architecture:** A pure numerical module owns calibration, metrics, threshold selection, and artifact validation. A separate experiment command collects validation/test logits, fits only on validation data, evaluates three fixed protocols on test data, and atomically writes reproducible artifacts under the project output directory. Runtime integration is gated on measured benefit.

**Tech Stack:** Python 3.8, PyTorch 2.0, NumPy, scikit-learn, existing CVB dataset/checkpoint loaders, pytest.

---

### Task 1: Numerical calibration primitives

**Files:**
- Create: `cattle_health_app/behavior/uncertainty.py`
- Create: `delivery_tests/test_behavior_uncertainty.py`

- [ ] **Step 1: Write failing validation and temperature-scaling tests**

Add tests proving that logits must be finite `N x 12`, labels must be in range, temperature is positive, temperature scaling preserves argmax, and fitting lowers NLL on an intentionally overconfident validation fixture.

- [ ] **Step 2: Run the focused test and verify failure**

Run: `F:\deepl\anaconda1\envs\pytorch\python.exe -m pytest delivery_tests/test_behavior_uncertainty.py -q`

Expected: collection fails because `cattle_health_app.behavior.uncertainty` does not exist.

- [ ] **Step 3: Implement validated temperature calibration**

Implement focused public functions:

```python
def probabilities_from_logits(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray: ...
def negative_log_likelihood(probabilities: np.ndarray, labels: np.ndarray) -> float: ...
def fit_temperature(logits: np.ndarray, labels: np.ndarray) -> float: ...
```

Use `torch.optim.LBFGS` over a scalar log-temperature, double precision CPU tensors, a bounded final temperature, and deterministic inputs.

- [ ] **Step 4: Run the focused test and verify pass**

Run the command from Step 2. Expected: all Task 1 tests pass.

- [ ] **Step 5: Commit Task 1**

Commit message: `feat: add behavior confidence calibration primitives`

### Task 2: Calibration and selective-prediction metrics

**Files:**
- Modify: `cattle_health_app/behavior/uncertainty.py`
- Modify: `delivery_tests/test_behavior_uncertainty.py`

- [ ] **Step 1: Write failing metric tests**

Add hand-computed fixtures for 15-bin ECE, multiclass Brier score, normalized entropy, coverage, selective accuracy/risk, selective Macro-F1, unsafe-prediction AUROC/AUPRC, and the zero-accepted-sample `None` contract.

- [ ] **Step 2: Run metric tests and verify failure**

Run: `F:\deepl\anaconda1\envs\pytorch\python.exe -m pytest delivery_tests/test_behavior_uncertainty.py -q`

Expected: failures identify the missing metric functions.

- [ ] **Step 3: Implement metrics with explicit schemas**

Add:

```python
def calibration_metrics(probabilities, labels, bins=15) -> dict: ...
def rejection_mask(probabilities, min_confidence, max_normalized_entropy) -> np.ndarray: ...
def selective_metrics(probabilities, labels, accepted, uncertain_label_ids=(0, 9, 10)) -> dict: ...
```

Use zero-based label IDs internally. Include overall metrics, accepted metrics, unsafe-detection metrics, and per-class counts. Return JSON-safe Python values.

- [ ] **Step 4: Run focused tests and verify pass**

Run the command from Step 2. Expected: all Task 1–2 tests pass.

- [ ] **Step 5: Commit Task 2**

Commit message: `feat: measure selective behavior prediction quality`

### Task 3: Validation-only rejection policy selection

**Files:**
- Modify: `cattle_health_app/behavior/uncertainty.py`
- Modify: `delivery_tests/test_behavior_uncertainty.py`

- [ ] **Step 1: Write failing deterministic policy-search tests**

Create a fixture with known confidence and entropy ordering. Assert minimum actionable coverage `0.60`, deterministic tie-breaking, rejection of invalid grids, and failure when no candidate meets coverage.

- [ ] **Step 2: Run policy tests and verify failure**

Run the focused pytest command. Expected: policy-selection tests fail because the selector is missing.

- [ ] **Step 3: Implement policy selection**

Add immutable `RejectionPolicy` and:

```python
def select_rejection_policy(
    probabilities,
    labels,
    confidence_grid,
    entropy_grid,
    minimum_actionable_coverage=0.60,
) -> RejectionPolicy: ...
```

Rank candidates by accepted Macro-F1 descending, selective risk ascending, actionable coverage descending, then thresholds ascending for deterministic ties.

- [ ] **Step 4: Run focused tests and verify pass**

Expected: all uncertainty module tests pass.

- [ ] **Step 5: Commit Task 3**

Commit message: `feat: select validation-only behavior rejection policy`

### Task 4: Offline experiment command and atomic artifacts

**Files:**
- Create: `cattle_health_app/behavior/uncertainty_experiment.py`
- Create: `delivery_tests/test_behavior_uncertainty_experiment.py`
- Modify: `scripts/train_cvb_behavior.ps1`

- [ ] **Step 1: Write failing orchestration tests with injected logits**

Test that fitting receives validation logits only, test metrics use the frozen policy, manifest/checkpoint hashes are recorded, duplicate sample IDs fail, output replacement is atomic, and two runs create identical core metrics.

- [ ] **Step 2: Run experiment tests and verify failure**

Run: `F:\deepl\anaconda1\envs\pytorch\python.exe -m pytest delivery_tests/test_behavior_uncertainty_experiment.py -q`

Expected: collection fails because the experiment module is missing.

- [ ] **Step 3: Implement inference and experiment orchestration**

The CLI accepts:

```text
--index-root --source-data-root --checkpoint --output-root
--device --batch-size --workers --seed
```

Load `val.csv` and `test.csv` through existing dataset code, collect logits and zero-based labels without augmentation, fit temperature/policy on validation, evaluate the three named protocols on test, and atomically publish:

```text
calibration.json
experiment_metrics.json
protocol_comparison.csv
test_predictions.csv
```

Do not serialize absolute external dataset paths in the portable metrics artifact; store manifest hashes and user-provided display names instead.

- [ ] **Step 4: Add the PowerShell experiment mode**

Extend the existing script with an `uncertainty` mode that invokes the new module and writes only below the selected project output root.

- [ ] **Step 5: Run focused orchestration tests**

Expected: all uncertainty experiment tests pass.

- [ ] **Step 6: Commit Task 4**

Commit message: `feat: add reproducible behavior uncertainty experiment`

### Task 5: Run the real validation/test experiment

**Files:**
- Create generated artifacts under: `outputs/uncertainty/cvb_x3d_v2/`
- Modify if results require factual updates: `README.md`

- [ ] **Step 1: Verify inputs without writing outside the project**

Check that the checkpoint hash matches the packaged model, validation/test manifests exist, all referenced frames resolve read-only, and the output root resolves under `F:\new大创`.

Record the measured full-test estimate (approximately 29.5 hours at 3.99 samples/second) and use the user-approved deterministic class-stratified caps: 512 validation and 1024 test samples per class with seed `20260823`.

- [ ] **Step 2: Run the experiment on validation and test splits**

Run the uncertainty command with the existing X3D v2 checkpoint, GPU device, prepared CVB v2 index, and the fixed sampling arguments. External CVB source data is read-only; all caches and artifacts point inside the project.

- [ ] **Step 3: Validate artifact consistency**

Recompute hashes, check JSON finiteness, verify test sample counts against the manifest, and confirm the policy in test results exactly matches `calibration.json`.

- [ ] **Step 4: Interpret results without cherry-picking**

Report all three protocols, including coverage. State a negative result if calibration or rejection does not improve the predefined success criteria.

- [ ] **Step 5: Commit reproducible code and small result tables**

Do not commit large per-sample files or logits. Commit the calibration artifact and compact comparison table only if repository ignore rules and licensing allow them.

### Task 6: Gate runtime integration on evidence

**Files:**
- Modify only if Task 5 meets success criteria: `cattle_health_app/behavior/runtime.py`
- Modify only if Task 5 meets success criteria: `cattle_health_app/media_processor.py`
- Modify only if Task 5 meets success criteria: `cattle_health_app/behavior/reporting.py`
- Test: `delivery_tests/test_behavior_runtime.py`
- Test: `delivery_tests/test_behavior_reporting.py`

- [ ] **Step 1: Decide from the predefined gate**

Integrate only if calibrated test NLL or ECE improves and the joint policy satisfies validation coverage. Record the decision and evidence in `experiment_metrics.json`.

- [ ] **Step 2: Write failing runtime artifact-loading tests if the gate passes**

Assert valid temperature/threshold loading, hash/version mismatch rejection, entropy-based rejection, preserved raw/smoothed fields, and fallback to existing behavior when no artifact is configured.

- [ ] **Step 3: Implement minimal runtime integration if the gate passes**

Apply temperature before runtime smoothing and apply the frozen confidence/entropy policy after smoothing. Add rejection reason and calibrated confidence to the report without changing legacy fields.

- [ ] **Step 4: Run behavior integration tests**

Run the uncertainty, runtime, reporting, tracking integration, API, and frontend contract tests.

- [ ] **Step 5: Commit or record the no-integration decision**

Use commit message `feat: apply calibrated behavior rejection policy` only when the evidence gate passes. Otherwise commit the experiment result documenting why runtime remains unchanged.

### Task 7: Final verification

**Files:**
- Modify: `README.md`
- Modify: `README_DELIVERY.md`

- [ ] **Step 1: Document exact claims and limitations**

Document validation-fit/test-evaluation separation, dataset-native uncertain labels, coverage trade-offs, model/checkpoint hashes, and the fact that this is not disease diagnosis or full open-set recognition.

- [ ] **Step 2: Run Python verification**

Run: `F:\deepl\anaconda1\envs\pytorch\python.exe -m pytest -q -p no:cacheprovider`

Expected: all project Python tests pass, with only documented skips.

- [ ] **Step 3: Run frontend verification**

Run in `web`: `npm test -- --run --reporter=dot` and `npm run build`.

Expected: 13 tests pass and production build exits successfully, unless newly added frontend tests intentionally increase the count.

- [ ] **Step 4: Run delivery preflight**

Run: `powershell -NoProfile -ExecutionPolicy Bypass -File .\start_delivery.ps1 -CheckOnly`

Expected: detector and behavior artifacts are ready and preflight passes.

- [ ] **Step 5: Review the final diff and artifact scope**

Confirm no file outside `F:\new大创` was modified and no external dataset, cache, large logits, or temporary test artifact was added to git.

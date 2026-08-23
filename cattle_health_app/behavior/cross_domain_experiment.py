"""Frozen cross-domain evaluation and validation-only quality gating."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable, Mapping, Sequence, Tuple

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score

from cattle_health_app.behavior.uncertainty import (
    probabilities_from_logits,
    rejection_mask,
    selective_metrics,
)


class ProtocolViolation(ValueError):
    """Raised when test-time evidence would alter the frozen protocol."""


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    try:
        return _sha256_bytes(path.read_bytes())
    except OSError as exc:
        raise ProtocolViolation("could not read frozen artifact: {}".format(exc)) from exc


def _validated_sha256(value, field: str) -> str:
    if not isinstance(value, str):
        raise ProtocolViolation("{} must be a SHA-256 string".format(field))
    normalized = value.lower()
    if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
        raise ProtocolViolation("{} must be a SHA-256 string".format(field))
    return normalized


def _unit_interval(value, field: str) -> float:
    if isinstance(value, bool):
        raise ProtocolViolation("{} must be within [0, 1]".format(field))
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ProtocolViolation("{} must be within [0, 1]".format(field)) from exc
    if not math.isfinite(parsed) or not 0.0 <= parsed <= 1.0:
        raise ProtocolViolation("{} must be within [0, 1]".format(field))
    return parsed


@dataclass(frozen=True)
class CrossDomainProtocol:
    checkpoint_sha256: str
    calibration_sha256: str
    validation_manifest_sha256: str
    temperature: float
    fixed_min_confidence: float
    fixed_max_normalized_entropy: float
    selection_split: str = "validation"

    def to_dict(self) -> dict:
        return asdict(self)


def load_frozen_protocol(checkpoint_path, calibration_path) -> CrossDomainProtocol:
    """Load calibration only when it is cryptographically bound to the checkpoint."""

    checkpoint = Path(checkpoint_path).expanduser().resolve()
    calibration = Path(calibration_path).expanduser().resolve()
    checkpoint_hash = _sha256_file(checkpoint)
    calibration_hash = _sha256_file(calibration)
    try:
        payload = json.loads(calibration.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProtocolViolation("could not parse calibration artifact: {}".format(exc)) from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ProtocolViolation("calibration schema_version must be 1")
    bound_hash = _validated_sha256(payload.get("checkpoint_sha256"), "checkpoint_sha256")
    if bound_hash != checkpoint_hash:
        raise ProtocolViolation(
            "checkpoint_sha256 mismatch: artifact={}, actual={}".format(
                bound_hash, checkpoint_hash
            )
        )
    if payload.get("selection_split") != "validation":
        raise ProtocolViolation("calibration must be selected on validation data")
    policy = payload.get("policy")
    if not isinstance(policy, dict) or policy.get("selection_split") != "validation":
        raise ProtocolViolation("rejection policy must be selected on validation data")
    try:
        temperature = float(payload.get("temperature"))
    except (TypeError, ValueError) as exc:
        raise ProtocolViolation("temperature must be finite and positive") from exc
    if not math.isfinite(temperature) or temperature <= 0.0:
        raise ProtocolViolation("temperature must be finite and positive")
    return CrossDomainProtocol(
        checkpoint_sha256=checkpoint_hash,
        calibration_sha256=calibration_hash,
        validation_manifest_sha256=_validated_sha256(
            payload.get("validation_manifest_sha256"), "validation_manifest_sha256"
        ),
        temperature=temperature,
        fixed_min_confidence=_unit_interval(
            policy.get("min_confidence"), "min_confidence"
        ),
        fixed_max_normalized_entropy=_unit_interval(
            policy.get("max_normalized_entropy"), "max_normalized_entropy"
        ),
    )


def _feature_matrix(
    rows: Iterable[Mapping[str, float]], feature_order: Sequence[str]
) -> np.ndarray:
    order = tuple(feature_order)
    if not order or any(not isinstance(name, str) or not name for name in order):
        raise ProtocolViolation("feature_order must contain named quality features")
    if len(set(order)) != len(order):
        raise ProtocolViolation("feature_order contains duplicates")
    materialized = tuple(rows)
    if not materialized:
        raise ProtocolViolation("quality feature rows must not be empty")
    matrix = []
    for row in materialized:
        if not isinstance(row, Mapping):
            raise ProtocolViolation("quality feature rows must be mappings")
        try:
            values = [float(row[name]) for name in order]
        except (KeyError, TypeError, ValueError) as exc:
            raise ProtocolViolation("quality feature row does not match feature_order") from exc
        if not all(math.isfinite(value) for value in values):
            raise ProtocolViolation("quality features must be finite")
        matrix.append(values)
    return np.asarray(matrix, dtype=np.float64)


@dataclass(frozen=True)
class QualityGate:
    feature_order: Tuple[str, ...]
    means: Tuple[float, ...]
    scales: Tuple[float, ...]
    coefficients: Tuple[float, ...]
    intercept: float
    acceptance_threshold: float
    minimum_eligible_coverage: float
    seed: int
    training_domain: str
    checkpoint_sha256: str
    input_manifest_sha256: str

    def scores(self, rows: Iterable[Mapping[str, float]]) -> np.ndarray:
        matrix = _feature_matrix(rows, self.feature_order)
        standardized = (matrix - np.asarray(self.means)) / np.asarray(self.scales)
        logits = standardized @ np.asarray(self.coefficients) + self.intercept
        positive = logits >= 0
        result = np.empty_like(logits)
        result[positive] = 1.0 / (1.0 + np.exp(-logits[positive]))
        exponentials = np.exp(logits[~positive])
        result[~positive] = exponentials / (1.0 + exponentials)
        return result

    def accept(self, rows: Iterable[Mapping[str, float]]) -> np.ndarray:
        return self.scores(rows) >= self.acceptance_threshold

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["feature_order"] = list(self.feature_order)
        payload["means"] = list(self.means)
        payload["scales"] = list(self.scales)
        payload["coefficients"] = list(self.coefficients)
        return payload


@dataclass(frozen=True)
class HeuristicQualityGate:
    """Absolute quality guard frozen without fitting any label-bearing rows."""

    checkpoint_sha256: str
    frozen_before_manifest_sha256: str
    minimum_brightness: float = 0.05
    maximum_brightness: float = 0.95
    maximum_dark_ratio: float = 0.85
    maximum_overexposed_ratio: float = 0.70
    minimum_laplacian_variance: float = 1e-5
    minimum_track_continuity: float = 0.95
    maximum_track_truncation_ratio: float = 0.75
    policy_kind: str = "predeclared_heuristic"
    uses_external_labels: bool = False

    def accept(self, rows: Iterable[Mapping[str, float]]) -> np.ndarray:
        fields = (
            "mean_brightness",
            "mean_dark_ratio",
            "mean_overexposed_ratio",
            "mean_laplacian_variance",
            "track_continuity",
            "track_truncation_ratio",
        )
        matrix = _feature_matrix(rows, fields)
        return (
            (matrix[:, 0] >= self.minimum_brightness)
            & (matrix[:, 0] <= self.maximum_brightness)
            & (matrix[:, 1] <= self.maximum_dark_ratio)
            & (matrix[:, 2] <= self.maximum_overexposed_ratio)
            & (matrix[:, 3] >= self.minimum_laplacian_variance)
            & (matrix[:, 4] >= self.minimum_track_continuity)
            & (matrix[:, 5] <= self.maximum_track_truncation_ratio)
        )

    def to_dict(self) -> dict:
        return asdict(self)


def freeze_heuristic_quality_gate(
    *, checkpoint_sha256: str, frozen_before_manifest_sha256: str
) -> HeuristicQualityGate:
    """Create the documented fallback without accepting labels or feature rows."""

    return HeuristicQualityGate(
        checkpoint_sha256=_validated_sha256(
            checkpoint_sha256, "checkpoint_sha256"
        ),
        frozen_before_manifest_sha256=_validated_sha256(
            frozen_before_manifest_sha256, "frozen_before_manifest_sha256"
        ),
    )


def _validated_targets(targets, count: int) -> np.ndarray:
    values = np.asarray(targets)
    if values.ndim != 1 or len(values) != count or values.dtype != np.bool_:
        raise ProtocolViolation("gate targets must be a boolean row-aligned array")
    if np.unique(values).size != 2:
        raise ProtocolViolation("gate targets must contain positive and negative examples")
    return values


def _select_gate_threshold(
    scores: np.ndarray, targets: np.ndarray, minimum_coverage: float
) -> float:
    candidates = sorted(set([0.0, 1.0] + [float(value) for value in scores]))
    ranked = []
    for threshold in candidates:
        accepted = scores >= threshold
        coverage = float(accepted.mean())
        if coverage + 1e-12 < minimum_coverage or not accepted.any():
            continue
        precision = float(targets[accepted].mean())
        ranked.append(((-precision, -coverage, threshold), threshold))
    if not ranked:
        raise ProtocolViolation("no gate threshold satisfies minimum eligible coverage")
    ranked.sort(key=lambda item: item[0])
    return float(ranked[0][1])


def fit_quality_gate(
    feature_rows: Iterable[Mapping[str, float]],
    eligible_correct_targets,
    *,
    feature_order: Sequence[str],
    training_domain: str,
    checkpoint_sha256: str,
    input_manifest_sha256: str,
    minimum_eligible_coverage: float = 0.60,
    seed: int = 20260823,
) -> QualityGate:
    """Fit an interpretable gate exclusively on frozen CVB validation evidence."""

    if training_domain != "cvb_validation":
        raise ProtocolViolation("quality gate training_domain must be cvb_validation")
    matrix = _feature_matrix(feature_rows, feature_order)
    targets = _validated_targets(eligible_correct_targets, len(matrix))
    minimum_coverage = _unit_interval(
        minimum_eligible_coverage, "minimum_eligible_coverage"
    )
    if minimum_coverage <= 0.0:
        raise ProtocolViolation("minimum_eligible_coverage must be positive")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ProtocolViolation("seed must be an integer")
    means = matrix.mean(axis=0)
    scales = matrix.std(axis=0)
    scales[scales <= np.finfo(np.float64).eps] = 1.0
    standardized = (matrix - means) / scales
    classifier = LogisticRegression(
        solver="liblinear", random_state=seed, max_iter=1000
    ).fit(standardized, targets.astype(np.int64))
    coefficients = classifier.coef_[0]
    intercept = float(classifier.intercept_[0])
    logits = standardized @ coefficients + intercept
    scores = 1.0 / (1.0 + np.exp(-logits))
    threshold = _select_gate_threshold(scores, targets, minimum_coverage)
    return QualityGate(
        feature_order=tuple(feature_order),
        means=tuple(float(value) for value in means),
        scales=tuple(float(value) for value in scales),
        coefficients=tuple(float(value) for value in coefficients),
        intercept=intercept,
        acceptance_threshold=threshold,
        minimum_eligible_coverage=minimum_coverage,
        seed=seed,
        training_domain=training_domain,
        checkpoint_sha256=_validated_sha256(
            checkpoint_sha256, "checkpoint_sha256"
        ),
        input_manifest_sha256=_validated_sha256(
            input_manifest_sha256, "input_manifest_sha256"
        ),
    )


@dataclass(frozen=True)
class ExternalPrediction:
    sample_id: str
    mapping_tier: str
    true_label: int
    logits: Tuple[float, ...]
    quality_features: Mapping[str, float]

    def __post_init__(self):
        if not isinstance(self.sample_id, str) or not self.sample_id:
            raise ProtocolViolation("sample_id must be non-empty text")
        if self.mapping_tier not in {"strict", "extended"}:
            raise ProtocolViolation("mapping_tier must be strict or extended")
        if isinstance(self.true_label, bool) or not isinstance(
            self.true_label, (int, np.integer)
        ):
            raise ProtocolViolation("true_label must be an integer")
        logits = np.asarray(self.logits, dtype=np.float64)
        if logits.ndim != 1 or len(logits) < 2 or not np.isfinite(logits).all():
            raise ProtocolViolation("logits must contain finite class scores")
        if not 0 <= int(self.true_label) < len(logits):
            raise ProtocolViolation("true_label is outside the logits class range")


VARIANT_NAMES = (
    "uncalibrated",
    "calibrated",
    "calibrated_fixed_rejection",
    "calibrated_quality_rejection",
)


def _probability_metrics(probabilities, labels, accepted) -> dict:
    selected = np.asarray(accepted, dtype=np.bool_)
    if not selected.any():
        return {
            "probability_metric_sample_count": 0,
            "accuracy": None,
            "nll": None,
            "ece": None,
            "brier": None,
        }
    values = probabilities[selected]
    targets = labels[selected]
    predictions = values.argmax(axis=1)
    confidence = values.max(axis=1)
    correct = predictions == targets
    epsilon = np.finfo(np.float64).tiny
    nll = -np.log(np.clip(values[np.arange(len(values)), targets], epsilon, 1.0))
    one_hot = np.zeros_like(values)
    one_hot[np.arange(len(values)), targets] = 1.0
    brier = np.square(values - one_hot).sum(axis=1)
    ece = 0.0
    edges = np.linspace(0.0, 1.0, 16)
    for index in range(len(edges) - 1):
        lower, upper = edges[index], edges[index + 1]
        in_bin = (confidence >= lower) & (
            confidence <= upper if index == len(edges) - 2 else confidence < upper
        )
        if in_bin.any():
            ece += float(in_bin.mean()) * abs(
                float(correct[in_bin].mean()) - float(confidence[in_bin].mean())
            )
    return {
        "probability_metric_sample_count": int(len(values)),
        "accuracy": float(correct.mean()),
        "nll": float(nll.mean()),
        "ece": float(ece),
        "brier": float(brier.mean()),
    }


def evaluate_variants(
    predictions: Sequence[ExternalPrediction],
    *,
    temperature: float,
    fixed_min_confidence: float,
    fixed_max_normalized_entropy: float,
    quality_gate: QualityGate,
    checkpoint_sha256: str = None,
) -> dict:
    """Evaluate four frozen variants separately for each mapping tier."""

    rows = tuple(predictions)
    if not rows:
        raise ProtocolViolation("external predictions must not be empty")
    sample_keys = [(row.mapping_tier, row.sample_id) for row in rows]
    if len(sample_keys) != len(set(sample_keys)):
        raise ProtocolViolation(
            "external prediction sample_id values must be unique within each mapping tier"
        )
    class_counts = {len(row.logits) for row in rows}
    if len(class_counts) != 1:
        raise ProtocolViolation("all external logits must use the same class count")
    if checkpoint_sha256 is not None and quality_gate.checkpoint_sha256 != _validated_sha256(
        checkpoint_sha256, "checkpoint_sha256"
    ):
        raise ProtocolViolation("quality gate checkpoint_sha256 mismatch")

    all_logits = np.asarray([row.logits for row in rows], dtype=np.float64)
    raw_probabilities = probabilities_from_logits(all_logits)
    calibrated_probabilities = probabilities_from_logits(all_logits, temperature)
    if not np.array_equal(
        raw_probabilities.argmax(axis=1), calibrated_probabilities.argmax(axis=1)
    ):
        raise ProtocolViolation("temperature calibration changed argmax predictions")
    fixed_accepted = ~rejection_mask(
        calibrated_probabilities,
        fixed_min_confidence,
        fixed_max_normalized_entropy,
    )
    quality_accepted = quality_gate.accept([row.quality_features for row in rows])
    acceptance = {
        "uncalibrated": np.ones(len(rows), dtype=np.bool_),
        "calibrated": np.ones(len(rows), dtype=np.bool_),
        "calibrated_fixed_rejection": fixed_accepted,
        "calibrated_quality_rejection": quality_accepted,
    }
    variant_probabilities = {
        "uncalibrated": raw_probabilities,
        "calibrated": calibrated_probabilities,
        "calibrated_fixed_rejection": calibrated_probabilities,
        "calibrated_quality_rejection": calibrated_probabilities,
    }

    metrics = {}
    for tier in ("strict", "extended"):
        selected = np.asarray([row.mapping_tier == tier for row in rows], dtype=np.bool_)
        if not selected.any():
            continue
        labels = np.asarray([row.true_label for row in rows], dtype=np.int64)[selected]
        eligible_label_ids = sorted(int(value) for value in np.unique(labels))
        metrics[tier] = {}
        for variant in VARIANT_NAMES:
            selected_acceptance = acceptance[variant][selected]
            metric = selective_metrics(
                variant_probabilities[variant][selected],
                labels,
                selected_acceptance,
                uncertain_label_ids=(),
            )
            metric.update(
                _probability_metrics(
                    variant_probabilities[variant][selected],
                    labels,
                    selected_acceptance,
                )
            )
            if selected_acceptance.any():
                predictions = variant_probabilities[variant][selected][
                    selected_acceptance
                ].argmax(axis=1)
                metric["selective_macro_f1"] = float(
                    f1_score(
                        labels[selected_acceptance],
                        predictions,
                        labels=eligible_label_ids,
                        average="macro",
                        zero_division=0,
                    )
                )
            metrics[tier][variant] = metric

    audit_rows = []
    for index, row in enumerate(rows):
        audit_rows.append(
            {
                "sample_id": row.sample_id,
                "mapping_tier": row.mapping_tier,
                "true_label": int(row.true_label),
                "raw_probabilities": [
                    float(value) for value in raw_probabilities[index]
                ],
                "calibrated_probabilities": [
                    float(value) for value in calibrated_probabilities[index]
                ],
                "accepted": {
                    variant: bool(acceptance[variant][index])
                    for variant in VARIANT_NAMES
                },
                "quality_features": dict(row.quality_features),
            }
        )
    return {"metrics": metrics, "predictions": audit_rows}

"""Calibration and selective-prediction utilities for behavior classifiers."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np
import torch
from sklearn.metrics import average_precision_score, f1_score, roc_auc_score
from torch.nn import functional as F


MIN_TEMPERATURE = 0.05
MAX_TEMPERATURE = 100.0


def _validated_logits(logits) -> np.ndarray:
    try:
        values = np.asarray(logits, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError("logits must be numeric") from exc
    if values.ndim != 2:
        raise ValueError("logits must be a two-dimensional array")
    if values.shape[0] == 0:
        raise ValueError("logits must contain at least one sample")
    if values.shape[1] < 2:
        raise ValueError("logits must contain at least two classes")
    if not np.isfinite(values).all():
        raise ValueError("logits must be finite")
    return values


def _validated_temperature(temperature) -> float:
    if isinstance(temperature, (bool, np.bool_)):
        raise TypeError("temperature must be a finite positive number")
    try:
        value = float(temperature)
    except (TypeError, ValueError) as exc:
        raise TypeError("temperature must be a finite positive number") from exc
    if not math.isfinite(value):
        raise ValueError("temperature must be finite")
    if value <= 0:
        raise ValueError("temperature must be positive")
    return value


def _validated_probabilities(probabilities) -> np.ndarray:
    try:
        values = np.asarray(probabilities, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError("probabilities must be numeric") from exc
    if values.ndim != 2 or values.shape[0] == 0 or values.shape[1] < 2:
        raise ValueError("probabilities must be a non-empty two-dimensional array")
    if not np.isfinite(values).all() or (values < 0).any() or (values > 1).any():
        raise ValueError("probabilities must be finite and in [0, 1]")
    if not np.allclose(values.sum(axis=1), 1.0, rtol=0.0, atol=1e-8):
        raise ValueError("probability rows must sum to one")
    return values


def _validated_labels(labels, sample_count: int, class_count: int) -> np.ndarray:
    values = np.asarray(labels)
    if values.ndim != 1:
        raise ValueError("labels must be one-dimensional")
    if len(values) != sample_count:
        raise ValueError("labels and predictions must contain the same number of samples")
    if not np.issubdtype(values.dtype, np.integer):
        raise ValueError("labels must use an integer dtype")
    values = values.astype(np.int64, copy=False)
    if (values < 0).any() or (values >= class_count).any():
        raise ValueError("labels must be in the class index range")
    return values


def probabilities_from_logits(logits, temperature: float = 1.0) -> np.ndarray:
    """Return stable softmax probabilities after scalar temperature scaling."""

    values = _validated_logits(logits)
    scale = _validated_temperature(temperature)
    adjusted = values / scale
    adjusted -= adjusted.max(axis=1, keepdims=True)
    exponentials = np.exp(adjusted)
    return exponentials / exponentials.sum(axis=1, keepdims=True)


def negative_log_likelihood(probabilities, labels) -> float:
    """Compute mean multiclass negative log-likelihood."""

    values = _validated_probabilities(probabilities)
    targets = _validated_labels(labels, len(values), values.shape[1])
    selected = values[np.arange(len(values)), targets]
    return float(-np.log(np.clip(selected, np.finfo(np.float64).tiny, 1.0)).mean())


def fit_temperature(logits, labels) -> float:
    """Fit one positive temperature by minimizing validation NLL on CPU."""

    values = _validated_logits(logits)
    targets = _validated_labels(labels, len(values), values.shape[1])
    logits_tensor = torch.as_tensor(values, dtype=torch.float64, device="cpu")
    labels_tensor = torch.as_tensor(targets, dtype=torch.long, device="cpu")
    log_temperature = torch.tensor(0.0, dtype=torch.float64, requires_grad=True)
    optimizer = torch.optim.LBFGS(
        [log_temperature], max_iter=100, tolerance_grad=1e-12,
        tolerance_change=1e-14, line_search_fn="strong_wolfe",
    )
    lower = math.log(MIN_TEMPERATURE)
    upper = math.log(MAX_TEMPERATURE)

    def closure():
        optimizer.zero_grad()
        bounded_log_temperature = torch.clamp(log_temperature, lower, upper)
        loss = F.cross_entropy(
            logits_tensor / torch.exp(bounded_log_temperature), labels_tensor
        )
        loss.backward()
        return loss

    optimizer.step(closure)
    fitted = math.exp(float(torch.clamp(log_temperature.detach(), lower, upper)))
    return min(MAX_TEMPERATURE, max(MIN_TEMPERATURE, fitted))


def normalized_entropy(probabilities) -> np.ndarray:
    """Return Shannon entropy normalized to [0, 1] by the class count."""

    values = _validated_probabilities(probabilities)
    positive = values > 0
    terms = np.zeros_like(values)
    terms[positive] = values[positive] * np.log(values[positive])
    return -terms.sum(axis=1) / math.log(values.shape[1])


def calibration_metrics(probabilities, labels, bins: int = 15) -> dict:
    """Measure multiclass classification and confidence calibration quality."""

    values = _validated_probabilities(probabilities)
    targets = _validated_labels(labels, len(values), values.shape[1])
    if isinstance(bins, bool) or not isinstance(bins, int) or bins <= 0:
        raise ValueError("bins must be a positive integer")
    predictions = values.argmax(axis=1)
    confidences = values.max(axis=1)
    correct = predictions == targets
    bin_ids = np.minimum((confidences * bins).astype(np.int64), bins - 1)
    ece = 0.0
    for bin_id in range(bins):
        selected = bin_ids == bin_id
        if selected.any():
            weight = float(selected.mean())
            gap = abs(float(correct[selected].mean()) - float(confidences[selected].mean()))
            ece += weight * gap
    one_hot = np.eye(values.shape[1], dtype=np.float64)[targets]
    brier = float(np.square(values - one_hot).sum(axis=1).mean())
    return {
        "sample_count": int(len(values)),
        "accuracy": float(correct.mean()),
        "macro_f1": float(
            f1_score(
                targets,
                predictions,
                labels=list(range(values.shape[1])),
                average="macro",
                zero_division=0,
            )
        ),
        "negative_log_likelihood": negative_log_likelihood(values, targets),
        "expected_calibration_error": float(ece),
        "multiclass_brier_score": brier,
        "ece_bins": bins,
    }


def _unit_interval(value, name: str) -> float:
    if isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be a finite number in [0, 1]")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be a finite number in [0, 1]") from exc
    if not math.isfinite(parsed) or not 0 <= parsed <= 1:
        raise ValueError(f"{name} must be in [0, 1]")
    return parsed


def rejection_mask(
    probabilities, min_confidence: float, max_normalized_entropy: float
) -> np.ndarray:
    """Return True for predictions rejected by either confidence gate."""

    values = _validated_probabilities(probabilities)
    confidence = _unit_interval(min_confidence, "min_confidence")
    entropy_limit = _unit_interval(
        max_normalized_entropy, "max_normalized_entropy"
    )
    return (values.max(axis=1) < confidence) | (
        normalized_entropy(values) > entropy_limit
    )


def _validated_accepted(accepted, sample_count: int) -> np.ndarray:
    values = np.asarray(accepted)
    if values.ndim != 1 or len(values) != sample_count:
        raise ValueError("accepted must be a one-dimensional sample mask")
    if values.dtype != np.bool_:
        raise ValueError("accepted must use a boolean dtype")
    return values


def _validated_uncertain_ids(values, class_count: int) -> tuple[int, ...]:
    if values is None:
        return ()
    parsed = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
            raise ValueError("uncertain_label_ids must contain integer class IDs")
        item = int(value)
        if item < 0 or item >= class_count:
            raise ValueError("uncertain_label_ids contains an out-of-range class ID")
        if item not in parsed:
            parsed.append(item)
    return tuple(parsed)


def selective_metrics(
    probabilities, labels, accepted, uncertain_label_ids=(0, 9, 10)
) -> dict:
    """Measure quality and safety trade-offs for a frozen acceptance mask."""

    values = _validated_probabilities(probabilities)
    targets = _validated_labels(labels, len(values), values.shape[1])
    accepted_mask = _validated_accepted(accepted, len(values))
    uncertain_ids = _validated_uncertain_ids(
        uncertain_label_ids, values.shape[1]
    )
    predictions = values.argmax(axis=1)
    correct = predictions == targets
    uncertain_truth = np.isin(targets, uncertain_ids)
    unsafe = uncertain_truth | ~correct
    rejected = ~accepted_mask
    actionable_truth = ~uncertain_truth
    actionable_count = int(actionable_truth.sum())
    accepted_count = int(accepted_mask.sum())
    unsafe_count = int(unsafe.sum())
    rejected_count = int(rejected.sum())

    if accepted_count:
        selective_accuracy = float(correct[accepted_mask].mean())
        selective_risk = 1.0 - selective_accuracy
    else:
        selective_accuracy = None
        selective_risk = None

    accepted_actionable = accepted_mask & actionable_truth
    actionable_ids = [
        item for item in range(values.shape[1]) if item not in uncertain_ids
    ]
    if accepted_actionable.any() and actionable_ids:
        selective_macro_f1 = float(
            f1_score(
                targets[accepted_actionable],
                predictions[accepted_actionable],
                labels=actionable_ids,
                average="macro",
                zero_division=0,
            )
        )
    else:
        selective_macro_f1 = None

    uncertainty_score = 1.0 - values.max(axis=1)
    if unsafe_count and unsafe_count < len(values):
        unsafe_auroc = float(roc_auc_score(unsafe, uncertainty_score))
        unsafe_auprc = float(average_precision_score(unsafe, uncertainty_score))
    else:
        unsafe_auroc = None
        unsafe_auprc = None

    per_class = []
    for class_id in range(values.shape[1]):
        selected = targets == class_id
        support = int(selected.sum())
        per_class.append(
            {
                "class_id": class_id,
                "support": support,
                "accepted": int((selected & accepted_mask).sum()),
                "rejected": int((selected & rejected).sum()),
            }
        )

    return {
        "sample_count": int(len(values)),
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "coverage": float(accepted_mask.mean()),
        "actionable_count": actionable_count,
        "actionable_coverage": (
            float((accepted_mask & actionable_truth).sum() / actionable_count)
            if actionable_count else None
        ),
        "selective_accuracy": selective_accuracy,
        "selective_macro_f1": selective_macro_f1,
        "selective_risk": selective_risk,
        "unsafe_count": unsafe_count,
        "unsafe_detection_score": "one_minus_max_probability",
        "unsafe_detection_auroc": unsafe_auroc,
        "unsafe_detection_auprc": unsafe_auprc,
        "rejection_precision_for_unsafe": (
            float((rejected & unsafe).sum() / rejected_count)
            if rejected_count else None
        ),
        "rejection_recall_for_unsafe": (
            float((rejected & unsafe).sum() / unsafe_count)
            if unsafe_count else None
        ),
        "per_class": per_class,
    }


@dataclass(frozen=True)
class RejectionPolicy:
    """A rejection policy selected exclusively from validation predictions."""

    min_confidence: float
    max_normalized_entropy: float
    minimum_actionable_coverage: float
    validation_actionable_coverage: float
    validation_selective_macro_f1: float
    validation_selective_risk: float
    selection_split: str = "validation"

    def to_dict(self) -> dict:
        return asdict(self)


def _validated_grid(values, name: str) -> tuple[float, ...]:
    try:
        items = list(values)
    except TypeError as exc:
        raise TypeError(f"{name} must be an iterable of thresholds") from exc
    if not items:
        raise ValueError(f"{name} must contain at least one threshold")
    return tuple(sorted({_unit_interval(item, name) for item in items}))


def select_rejection_policy(
    probabilities,
    labels,
    confidence_grid,
    entropy_grid,
    minimum_actionable_coverage: float = 0.60,
    uncertain_label_ids=(0, 9, 10),
) -> RejectionPolicy:
    """Select a deterministic joint rejection policy using validation data."""

    values = _validated_probabilities(probabilities)
    targets = _validated_labels(labels, len(values), values.shape[1])
    confidence_values = _validated_grid(confidence_grid, "confidence_grid")
    entropy_values = _validated_grid(entropy_grid, "entropy_grid")
    minimum_coverage = _unit_interval(
        minimum_actionable_coverage, "minimum_actionable_coverage"
    )
    uncertain_ids = _validated_uncertain_ids(
        uncertain_label_ids, values.shape[1]
    )
    candidates = []
    for confidence in confidence_values:
        for entropy_limit in entropy_values:
            accepted = ~rejection_mask(values, confidence, entropy_limit)
            metrics = selective_metrics(
                values, targets, accepted, uncertain_label_ids=uncertain_ids
            )
            coverage = metrics["actionable_coverage"]
            macro_f1 = metrics["selective_macro_f1"]
            risk = metrics["selective_risk"]
            if (
                coverage is None
                or coverage + 1e-12 < minimum_coverage
                or macro_f1 is None
                or risk is None
            ):
                continue
            policy = RejectionPolicy(
                min_confidence=confidence,
                max_normalized_entropy=entropy_limit,
                minimum_actionable_coverage=minimum_coverage,
                validation_actionable_coverage=float(coverage),
                validation_selective_macro_f1=float(macro_f1),
                validation_selective_risk=float(risk),
            )
            rank = (
                -float(macro_f1),
                float(risk),
                -float(coverage),
                confidence,
                entropy_limit,
            )
            candidates.append((rank, policy))
    if not candidates:
        raise ValueError(
            "no rejection policy satisfies minimum actionable coverage"
        )
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]

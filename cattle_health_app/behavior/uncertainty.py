"""Calibration and selective-prediction utilities for behavior classifiers."""

from __future__ import annotations

import math

import numpy as np
import torch
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

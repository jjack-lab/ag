import numpy as np
import pytest

from cattle_health_app.behavior.uncertainty import (
    fit_temperature,
    negative_log_likelihood,
    probabilities_from_logits,
)


def overconfident_fixture():
    logits = np.array(
        [
            [8.0, 0.0, 0.0],
            [0.0, 8.0, 0.0],
            [8.0, 0.0, 0.0],
            [0.0, 8.0, 0.0],
            [8.0, 0.0, 0.0],
            [0.0, 8.0, 0.0],
        ],
        dtype=np.float64,
    )
    labels = np.array([0, 1, 0, 1, 1, 0], dtype=np.int64)
    return logits, labels


def test_temperature_scaling_preserves_argmax_and_normalizes_rows():
    logits, _ = overconfident_fixture()

    original = probabilities_from_logits(logits)
    softened = probabilities_from_logits(logits, temperature=2.5)

    np.testing.assert_array_equal(original.argmax(axis=1), softened.argmax(axis=1))
    np.testing.assert_allclose(softened.sum(axis=1), 1.0)
    assert np.all(softened.max(axis=1) < original.max(axis=1))


@pytest.mark.parametrize(
    "logits,temperature,match",
    [
        (np.zeros(3), 1.0, "two-dimensional"),
        (np.zeros((2, 1)), 1.0, "at least two classes"),
        (np.array([[0.0, np.nan]]), 1.0, "finite"),
        (np.zeros((2, 3)), 0.0, "positive"),
        (np.zeros((2, 3)), np.inf, "finite"),
    ],
)
def test_probabilities_from_logits_rejects_invalid_inputs(logits, temperature, match):
    with pytest.raises((TypeError, ValueError), match=match):
        probabilities_from_logits(logits, temperature)


def test_negative_log_likelihood_validates_labels_and_probabilities():
    probabilities = np.array([[0.8, 0.2], [0.25, 0.75]], dtype=np.float64)
    labels = np.array([0, 1], dtype=np.int64)

    expected = -np.log([0.8, 0.75]).mean()
    assert negative_log_likelihood(probabilities, labels) == pytest.approx(expected)

    with pytest.raises(ValueError, match="same number"):
        negative_log_likelihood(probabilities, labels[:1])
    with pytest.raises(ValueError, match="integer"):
        negative_log_likelihood(probabilities, labels.astype(np.float64))
    with pytest.raises(ValueError, match="range"):
        negative_log_likelihood(probabilities, np.array([0, 2]))
    with pytest.raises(ValueError, match="sum to one"):
        negative_log_likelihood(np.array([[0.8, 0.3], [0.2, 0.8]]), labels)


def test_fit_temperature_reduces_validation_nll_and_is_deterministic():
    logits, labels = overconfident_fixture()
    uncalibrated = probabilities_from_logits(logits)

    first = fit_temperature(logits, labels)
    second = fit_temperature(logits, labels)
    calibrated = probabilities_from_logits(logits, first)

    assert first == pytest.approx(second, rel=0, abs=1e-12)
    assert 1.0 < first <= 100.0
    assert negative_log_likelihood(calibrated, labels) < negative_log_likelihood(
        uncalibrated, labels
    )

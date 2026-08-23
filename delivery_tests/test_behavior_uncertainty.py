import numpy as np
import pytest

from cattle_health_app.behavior.uncertainty import (
    calibration_metrics,
    fit_temperature,
    negative_log_likelihood,
    normalized_entropy,
    probabilities_from_logits,
    rejection_mask,
    select_rejection_policy,
    selective_metrics,
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


def test_calibration_metrics_match_hand_computed_values():
    probabilities = np.array([[0.8, 0.2], [0.4, 0.6]], dtype=np.float64)
    labels = np.array([0, 0], dtype=np.int64)

    metrics = calibration_metrics(probabilities, labels, bins=2)

    assert metrics["negative_log_likelihood"] == pytest.approx(
        -np.log([0.8, 0.4]).mean()
    )
    assert metrics["expected_calibration_error"] == pytest.approx(0.2)
    assert metrics["multiclass_brier_score"] == pytest.approx(0.4)
    assert metrics["accuracy"] == pytest.approx(0.5)
    assert metrics["macro_f1"] == pytest.approx(1.0 / 3.0)


def test_calibration_metrics_reject_invalid_bin_count():
    with pytest.raises(ValueError, match="bins"):
        calibration_metrics(np.array([[0.5, 0.5]]), np.array([0]), bins=0)


def test_normalized_entropy_has_zero_and_unit_endpoints():
    probabilities = np.array([[1.0, 0.0], [0.5, 0.5]], dtype=np.float64)

    entropy = normalized_entropy(probabilities)

    np.testing.assert_allclose(entropy, [0.0, 1.0], atol=1e-12)


def test_joint_rejection_uses_low_confidence_or_high_entropy():
    probabilities = np.array(
        [[0.9, 0.1], [0.6, 0.4], [0.55, 0.45]], dtype=np.float64
    )

    rejected = rejection_mask(
        probabilities, min_confidence=0.65, max_normalized_entropy=0.99
    )

    np.testing.assert_array_equal(rejected, [False, True, True])


@pytest.mark.parametrize(
    "confidence,entropy,match",
    [(-0.1, 0.5, "min_confidence"), (0.5, 1.1, "max_normalized_entropy")],
)
def test_joint_rejection_validates_thresholds(confidence, entropy, match):
    with pytest.raises(ValueError, match=match):
        rejection_mask(np.array([[0.5, 0.5]]), confidence, entropy)


def test_selective_metrics_report_coverage_risk_and_per_class_counts():
    probabilities = np.array(
        [
            [0.9, 0.05, 0.05],
            [0.2, 0.7, 0.1],
            [0.6, 0.3, 0.1],
            [0.1, 0.2, 0.7],
        ],
        dtype=np.float64,
    )
    labels = np.array([0, 1, 1, 2], dtype=np.int64)
    accepted = np.array([True, True, False, False])

    metrics = selective_metrics(
        probabilities, labels, accepted, uncertain_label_ids=(2,)
    )

    assert metrics["sample_count"] == 4
    assert metrics["coverage"] == pytest.approx(0.5)
    assert metrics["actionable_coverage"] == pytest.approx(2.0 / 3.0)
    assert metrics["selective_accuracy"] == pytest.approx(1.0)
    assert metrics["selective_risk"] == pytest.approx(0.0)
    assert metrics["selective_macro_f1"] == pytest.approx(1.0)
    assert metrics["unsafe_count"] == 2
    assert metrics["rejection_recall_for_unsafe"] == pytest.approx(1.0)
    assert metrics["per_class"] == [
        {"class_id": 0, "support": 1, "accepted": 1, "rejected": 0},
        {"class_id": 1, "support": 2, "accepted": 1, "rejected": 1},
        {"class_id": 2, "support": 1, "accepted": 0, "rejected": 1},
    ]
    assert 0.0 <= metrics["unsafe_detection_auroc"] <= 1.0
    assert 0.0 <= metrics["unsafe_detection_auprc"] <= 1.0


def test_selective_metrics_use_null_when_nothing_is_accepted():
    probabilities = np.array([[0.8, 0.2], [0.3, 0.7]], dtype=np.float64)
    labels = np.array([0, 1], dtype=np.int64)

    metrics = selective_metrics(
        probabilities, labels, np.array([False, False]), uncertain_label_ids=()
    )

    assert metrics["coverage"] == 0.0
    assert metrics["selective_accuracy"] is None
    assert metrics["selective_macro_f1"] is None
    assert metrics["selective_risk"] is None


def test_selective_metrics_exclude_predictions_of_dataset_uncertain_classes():
    probabilities = np.array(
        [[0.1, 0.1, 0.8], [0.1, 0.8, 0.1]], dtype=np.float64
    )
    labels = np.array([0, 1], dtype=np.int64)

    metrics = selective_metrics(
        probabilities,
        labels,
        np.array([True, True]),
        uncertain_label_ids=(2,),
    )

    assert metrics["threshold_accepted_count"] == 2
    assert metrics["accepted_count"] == 1
    assert metrics["coverage"] == pytest.approx(0.5)
    assert metrics["actionable_coverage"] == pytest.approx(0.5)
    assert metrics["rejection_recall_for_unsafe"] == pytest.approx(1.0)


def policy_fixture():
    probabilities = np.array(
        [
            [0.90, 0.05, 0.05],
            [0.55, 0.40, 0.05],
            [0.10, 0.80, 0.10],
            [0.45, 0.50, 0.05],
            [0.40, 0.50, 0.10],
            [0.20, 0.20, 0.60],
        ],
        dtype=np.float64,
    )
    labels = np.array([0, 0, 1, 1, 0, 2], dtype=np.int64)
    return probabilities, labels


def test_policy_search_maximizes_macro_f1_at_required_actionable_coverage():
    probabilities, labels = policy_fixture()

    policy = select_rejection_policy(
        probabilities,
        labels,
        confidence_grid=[0.0, 0.55],
        entropy_grid=[1.0],
        minimum_actionable_coverage=0.60,
        uncertain_label_ids=(2,),
    )

    assert policy.min_confidence == pytest.approx(0.55)
    assert policy.max_normalized_entropy == pytest.approx(1.0)
    assert policy.minimum_actionable_coverage == pytest.approx(0.60)
    assert policy.validation_actionable_coverage == pytest.approx(0.60)
    assert policy.validation_selective_macro_f1 == pytest.approx(1.0)
    assert policy.validation_selective_risk == pytest.approx(0.0)
    assert policy.to_dict()["selection_split"] == "validation"


def test_policy_search_is_deterministic_for_unsorted_grids():
    probabilities, labels = policy_fixture()

    first = select_rejection_policy(
        probabilities,
        labels,
        confidence_grid=[0.55, 0.0, 0.55],
        entropy_grid=[1.0, 0.99],
        minimum_actionable_coverage=0.60,
        uncertain_label_ids=(2,),
    )
    second = select_rejection_policy(
        probabilities,
        labels,
        confidence_grid=[0.0, 0.55],
        entropy_grid=[0.99, 1.0],
        minimum_actionable_coverage=0.60,
        uncertain_label_ids=(2,),
    )

    assert first == second


def test_policy_search_fails_instead_of_relaxing_coverage():
    probabilities, labels = policy_fixture()

    with pytest.raises(ValueError, match="coverage"):
        select_rejection_policy(
            probabilities,
            labels,
            confidence_grid=[0.95],
            entropy_grid=[0.0],
            minimum_actionable_coverage=0.60,
            uncertain_label_ids=(2,),
        )


@pytest.mark.parametrize(
    "confidence_grid,entropy_grid,coverage,match",
    [([], [1.0], 0.6, "confidence_grid"), ([0.5], [], 0.6, "entropy_grid"),
     ([0.5], [1.0], 1.1, "minimum_actionable_coverage")],
)
def test_policy_search_validates_candidate_space(
    confidence_grid, entropy_grid, coverage, match
):
    probabilities, labels = policy_fixture()

    with pytest.raises(ValueError, match=match):
        select_rejection_policy(
            probabilities,
            labels,
            confidence_grid,
            entropy_grid,
            minimum_actionable_coverage=coverage,
            uncertain_label_ids=(2,),
        )

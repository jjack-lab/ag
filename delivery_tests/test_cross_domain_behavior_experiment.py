import hashlib
import json

import numpy as np
import pytest

from cattle_health_app.behavior.cross_domain_experiment import (
    ExternalPrediction,
    ProtocolViolation,
    evaluate_variants,
    fit_quality_gate,
    freeze_heuristic_quality_gate,
    load_frozen_protocol,
)


def _sha256(payload):
    return hashlib.sha256(payload).hexdigest()


def _write_calibration(path, checkpoint_hash):
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "checkpoint_sha256": checkpoint_hash,
                "validation_manifest_sha256": "b" * 64,
                "selection_split": "validation",
                "temperature": 2.0,
                "policy": {
                    "selection_split": "validation",
                    "min_confidence": 0.45,
                    "max_normalized_entropy": 0.85,
                },
            }
        ),
        encoding="utf-8",
    )


def _features(brightness, continuity):
    return {
        "mean_brightness": brightness,
        "track_continuity": continuity,
    }


def test_gate_fit_rejects_external_training_domain():
    with pytest.raises(ProtocolViolation, match="cvb_validation"):
        fit_quality_gate(
            [_features(0.8, 1.0), _features(0.2, 0.5)],
            [True, False],
            feature_order=("mean_brightness", "track_continuity"),
            training_domain="cbvd5_test",
            checkpoint_sha256="a" * 64,
            input_manifest_sha256="b" * 64,
        )


def test_fitted_gate_records_the_frozen_training_evidence():
    rows = [
        _features(0.90, 1.00),
        _features(0.80, 0.95),
        _features(0.70, 0.90),
        _features(0.30, 0.60),
        _features(0.20, 0.50),
        _features(0.10, 0.40),
    ]
    gate = fit_quality_gate(
        rows,
        [True, True, True, False, False, False],
        feature_order=("mean_brightness", "track_continuity"),
        training_domain="cvb_validation",
        checkpoint_sha256="a" * 64,
        input_manifest_sha256="b" * 64,
        minimum_eligible_coverage=0.5,
        seed=20260823,
    )

    payload = gate.to_dict()
    assert payload["training_domain"] == "cvb_validation"
    assert payload["checkpoint_sha256"] == "a" * 64
    assert payload["input_manifest_sha256"] == "b" * 64
    assert payload["feature_order"] == ["mean_brightness", "track_continuity"]
    assert 0.0 <= payload["acceptance_threshold"] <= 1.0
    assert gate.accept(rows).dtype == np.bool_


def test_predeclared_quality_guard_uses_absolute_rules_without_labels():
    gate = freeze_heuristic_quality_gate(
        checkpoint_sha256="a" * 64,
        frozen_before_manifest_sha256="b" * 64,
    )
    rows = [
        {
            "mean_brightness": 0.45,
            "mean_dark_ratio": 0.10,
            "mean_overexposed_ratio": 0.05,
            "mean_laplacian_variance": 0.02,
            "track_continuity": 1.0,
            "track_truncation_ratio": 0.0,
        },
        {
            "mean_brightness": 0.02,
            "mean_dark_ratio": 0.95,
            "mean_overexposed_ratio": 0.0,
            "mean_laplacian_variance": 0.0,
            "track_continuity": 1.0,
            "track_truncation_ratio": 0.0,
        },
    ]

    assert gate.accept(rows).tolist() == [True, False]
    payload = gate.to_dict()
    assert payload["policy_kind"] == "predeclared_heuristic"
    assert payload["uses_external_labels"] is False
    assert payload["frozen_before_manifest_sha256"] == "b" * 64


def test_frozen_protocol_rejects_calibration_hash_mismatch(tmp_path):
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"frozen-checkpoint")
    calibration = tmp_path / "calibration.json"
    _write_calibration(calibration, "0" * 64)

    with pytest.raises(ProtocolViolation, match="checkpoint_sha256"):
        load_frozen_protocol(checkpoint, calibration)


def test_frozen_protocol_records_checkpoint_and_calibration_hashes(tmp_path):
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"frozen-checkpoint")
    calibration = tmp_path / "calibration.json"
    _write_calibration(calibration, _sha256(b"frozen-checkpoint"))

    protocol = load_frozen_protocol(checkpoint, calibration)

    assert protocol.checkpoint_sha256 == _sha256(b"frozen-checkpoint")
    assert protocol.calibration_sha256 == _sha256(calibration.read_bytes())
    assert protocol.validation_manifest_sha256 == "b" * 64
    assert protocol.temperature == pytest.approx(2.0)


def _prediction(sample_id, tier, true_label, predicted_label, confidence):
    remaining = (1.0 - confidence) / 11.0
    probabilities = np.full(12, remaining, dtype=np.float64)
    probabilities[predicted_label] = confidence
    logits = np.log(probabilities)
    return ExternalPrediction(
        sample_id=sample_id,
        mapping_tier=tier,
        true_label=true_label,
        logits=tuple(logits),
        quality_features=_features(0.8, 0.9),
    )


def test_variants_are_exact_and_mapping_tiers_remain_separate():
    predictions = [
        _prediction("strict-correct", "strict", 0, 0, 0.9),
        _prediction("strict-wrong", "strict", 0, 1, 0.8),
        _prediction("strict-correct", "extended", 1, 1, 0.7),
    ]
    gate = fit_quality_gate(
        [_features(0.9, 1.0), _features(0.8, 0.9), _features(0.2, 0.4), _features(0.1, 0.3)],
        [True, True, False, False],
        feature_order=("mean_brightness", "track_continuity"),
        training_domain="cvb_validation",
        checkpoint_sha256="a" * 64,
        input_manifest_sha256="b" * 64,
        minimum_eligible_coverage=0.5,
    )

    result = evaluate_variants(
        predictions,
        temperature=2.0,
        fixed_min_confidence=0.45,
        fixed_max_normalized_entropy=0.85,
        quality_gate=gate,
    )

    expected = {
        "uncalibrated",
        "calibrated",
        "calibrated_fixed_rejection",
        "calibrated_quality_rejection",
    }
    assert set(result["metrics"]) == {"strict", "extended"}
    assert set(result["metrics"]["strict"]) == expected
    assert result["metrics"]["strict"]["uncalibrated"]["sample_count"] == 2
    assert result["metrics"]["strict"]["uncalibrated"]["selective_risk"] == pytest.approx(0.5)
    assert result["metrics"]["strict"]["uncalibrated"][
        "selective_macro_f1"
    ] == pytest.approx(2 / 3)
    assert result["metrics"]["strict"]["uncalibrated"]["accuracy"] == pytest.approx(
        0.5
    )
    for field in ("nll", "ece", "brier"):
        assert np.isfinite(result["metrics"]["strict"]["uncalibrated"][field])
    assert result["metrics"]["extended"]["uncalibrated"]["sample_count"] == 1
    assert result["metrics"]["extended"]["uncalibrated"][
        "selective_macro_f1"
    ] == pytest.approx(1.0)
    assert len(result["predictions"][0]["raw_probabilities"]) == 12
    assert result["predictions"][0]["mapping_tier"] == "strict"

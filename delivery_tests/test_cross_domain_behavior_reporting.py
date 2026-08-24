import csv
import json
from pathlib import Path

import pytest

from cattle_health_app.behavior.cross_domain_reporting import write_cross_domain_report


def _evaluation():
    predictions = [
        {
            "sample_id": "a",
            "mapping_tier": "strict",
            "true_label": 0,
            "raw_probabilities": [0.9, 0.1],
            "calibrated_probabilities": [0.8, 0.2],
            "accepted": {
                "uncalibrated": True,
                "calibrated": True,
                "calibrated_fixed_rejection": True,
                "calibrated_quality_rejection": True,
            },
            "quality_features": {"track_continuity": 1.0},
        },
        {
            "sample_id": "b",
            "mapping_tier": "strict",
            "true_label": 0,
            "raw_probabilities": [0.2, 0.8],
            "calibrated_probabilities": [0.3, 0.7],
            "accepted": {
                "uncalibrated": True,
                "calibrated": True,
                "calibrated_fixed_rejection": False,
                "calibrated_quality_rejection": False,
            },
            "quality_features": {"track_continuity": 0.5},
        },
    ]
    metrics = {
        "strict": {
            "uncalibrated": {
                "sample_count": 2,
                "accepted_count": 2,
                "coverage": 1.0,
                "selective_accuracy": 0.5,
                "selective_macro_f1": 1 / 3,
                "selective_risk": 0.5,
            },
            "calibrated": {
                "sample_count": 2,
                "accepted_count": 2,
                "coverage": 1.0,
                "selective_accuracy": 0.5,
                "selective_macro_f1": 1 / 3,
                "selective_risk": 0.5,
            },
            "calibrated_fixed_rejection": {
                "sample_count": 2,
                "accepted_count": 1,
                "coverage": 0.5,
                "selective_accuracy": 1.0,
                "selective_macro_f1": 0.5,
                "selective_risk": 0.0,
            },
            "calibrated_quality_rejection": {
                "sample_count": 2,
                "accepted_count": 1,
                "coverage": 0.5,
                "selective_accuracy": 1.0,
                "selective_macro_f1": 0.5,
                "selective_risk": 0.0,
            },
        }
    }
    return {"predictions": predictions, "metrics": metrics}


def _protocol():
    return {
        "checkpoint_sha256": "a" * 64,
        "calibration_sha256": "b" * 64,
        "manifest_sha256": "c" * 64,
        "dataset_id": "cbvd5",
        "dataset_version": "11",
        "seed": 20260823,
    }


def _timing():
    return {
        "schema_version": 1,
        "protocol_fingerprint": "d" * 64,
        "baseline": {
            "wall_seconds": 2.0,
            "logical_sample_count": 2,
            "physical_clip_count": 2,
            "logical_samples_per_second": 1.0,
            "device": "cpu",
        },
        "stress": [],
    }


def test_reporting_writes_machine_readable_and_paper_ready_artifacts(tmp_path):
    output = tmp_path / "report"
    stress = [
        {
            "mapping_tier": "strict",
            "variant": "calibrated_quality_rejection",
            "degradation": "blur",
            "level": 1,
            "sample_count": 2,
            "macro_f1": 0.4,
            "coverage": 0.5,
        }
    ]

    summary = write_cross_domain_report(
        output,
        protocol=_protocol(),
        evaluation=_evaluation(),
        stress_rows=stress,
        class_names=("grazing", "drinking"),
        inference_timing=_timing(),
    )

    expected = {
        "predictions.csv",
        "metrics.json",
        "protocol_comparison.csv",
        "per_class_metrics.csv",
        "risk_coverage.csv",
        "stress_metrics.csv",
        "confusion_matrix.png",
        "risk_coverage.png",
        "stress_curves.png",
        "summary.md",
    }
    assert {path.name for path in output.iterdir()} == expected
    assert summary["status"] == "complete"
    assert (output / "confusion_matrix.png").read_bytes().startswith(b"\x89PNG")
    metrics = json.loads((output / "metrics.json").read_text("utf-8"))
    assert metrics["sample_counts"] == {"strict": 2}


def test_protocol_table_keeps_sample_count_next_to_every_metric(tmp_path):
    output = tmp_path / "report"
    write_cross_domain_report(
        output,
        protocol=_protocol(),
        evaluation=_evaluation(),
        stress_rows=[],
        class_names=("grazing", "drinking"),
        inference_timing=_timing(),
    )

    with (output / "protocol_comparison.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    quality = next(row for row in rows if row["variant"] == "calibrated_quality_rejection")
    assert quality["sample_count"] == "2"
    assert quality["accepted_count"] == "1"
    assert quality["coverage"] == "0.5"
    assert quality["selective_risk"] == "0.0"

    with (output / "per_class_metrics.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        per_class = list(csv.DictReader(handle))
    uncalibrated = next(
        row
        for row in per_class
        if row["variant"] == "uncalibrated" and row["class_name"] == "grazing"
    )
    assert uncalibrated["support"] == "2"
    assert uncalibrated["accepted_support"] == "2"
    assert float(uncalibrated["precision"]) == 1.0
    assert float(uncalibrated["recall"]) == 0.5
    assert float(uncalibrated["f1"]) == pytest.approx(2 / 3)


def test_summary_states_claim_boundaries_and_external_sample_count(tmp_path):
    output = tmp_path / "report"
    write_cross_domain_report(
        output,
        protocol=_protocol(),
        evaluation=_evaluation(),
        stress_rows=[],
        class_names=("grazing", "drinking"),
        inference_timing=_timing(),
    )

    markdown = (output / "summary.md").read_text("utf-8")
    assert "n=2" in markdown
    assert "不支持" in markdown
    assert "疾病诊断" in markdown
    assert "外部测试集" in markdown
    metrics = json.loads((output / "metrics.json").read_text("utf-8"))
    assert metrics["inference_timing"]["baseline"]["wall_seconds"] == 2.0


def test_committed_result_document_records_verified_complete_evidence():
    project_root = Path(__file__).resolve().parents[1]
    document = (
        project_root
        / "docs"
        / "experiments"
        / "2026-08-23-cross-domain-behavior-results.md"
    ).read_text(encoding="utf-8")

    assert "status: complete" in document
    assert "731c6ed39dcf002915e888c829e1f86727f815331a2b3c21d06a17d40d62a08e" in document
    assert "Strict 主结果（4 类，n=400）" in document
    assert "现有 CVB 模型不能直接迁移到 CBVD-5" in document
    assert "不支持疾病诊断" in document
    assert "VLM" in document

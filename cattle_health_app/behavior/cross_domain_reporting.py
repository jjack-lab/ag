"""Paper-ready, claim-bounded reporting for cross-domain behavior experiments."""

import csv
import json
import math
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


class ReportingError(ValueError):
    pass


VARIANTS = (
    "uncalibrated",
    "calibrated",
    "calibrated_fixed_rejection",
    "calibrated_quality_rejection",
)


def _write_json(path: Path, payload) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, fields, rows: Iterable[Mapping[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _validated_probability_row(value, class_count: int, field: str) -> np.ndarray:
    try:
        row = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ReportingError("{} must contain numeric probabilities".format(field)) from exc
    if (
        row.ndim != 1
        or len(row) != class_count
        or not np.isfinite(row).all()
        or (row < 0).any()
        or not math.isclose(float(row.sum()), 1.0, rel_tol=0.0, abs_tol=1e-6)
    ):
        raise ReportingError("{} must be a normalized class row".format(field))
    return row


def _validated_predictions(predictions, class_names: Sequence[str]):
    class_count = len(class_names)
    if class_count < 2 or len(set(class_names)) != class_count:
        raise ReportingError("class_names must contain at least two unique labels")
    rows = []
    sample_ids = set()
    for source in predictions:
        if not isinstance(source, Mapping):
            raise ReportingError("prediction rows must be mappings")
        sample_id = source.get("sample_id")
        tier = source.get("mapping_tier")
        true_label = source.get("true_label")
        if not isinstance(sample_id, str) or not sample_id or sample_id in sample_ids:
            raise ReportingError("prediction sample_id values must be unique and non-empty")
        if tier not in {"strict", "extended"}:
            raise ReportingError("prediction mapping_tier must be strict or extended")
        if isinstance(true_label, bool) or not isinstance(true_label, int) or not 0 <= true_label < class_count:
            raise ReportingError("prediction true_label is outside class_names")
        accepted = source.get("accepted")
        if not isinstance(accepted, Mapping) or set(accepted) != set(VARIANTS):
            raise ReportingError("prediction accepted flags must match frozen variants")
        if any(not isinstance(accepted[name], bool) for name in VARIANTS):
            raise ReportingError("prediction accepted flags must be boolean")
        raw = _validated_probability_row(source.get("raw_probabilities"), class_count, "raw_probabilities")
        calibrated = _validated_probability_row(
            source.get("calibrated_probabilities"), class_count, "calibrated_probabilities"
        )
        sample_ids.add(sample_id)
        rows.append(
            {
                "source": source,
                "sample_id": sample_id,
                "mapping_tier": tier,
                "true_label": true_label,
                "raw": raw,
                "calibrated": calibrated,
                "accepted": accepted,
            }
        )
    if not rows:
        raise ReportingError("at least one prediction is required")
    return rows


def _validate_metric_counts(metrics, rows) -> dict:
    counts = {}
    for tier in ("strict", "extended"):
        count = sum(row["mapping_tier"] == tier for row in rows)
        if not count:
            continue
        counts[tier] = count
        tier_metrics = metrics.get(tier)
        if not isinstance(tier_metrics, Mapping) or set(tier_metrics) != set(VARIANTS):
            raise ReportingError("metrics must contain four variants for {}".format(tier))
        for variant in VARIANTS:
            metric = tier_metrics[variant]
            if metric.get("sample_count") != count:
                raise ReportingError("metric sample_count does not match predictions")
            accepted = sum(
                row["mapping_tier"] == tier and row["accepted"][variant] for row in rows
            )
            if metric.get("accepted_count") != accepted:
                raise ReportingError("metric accepted_count does not match predictions")
            coverage = accepted / float(count)
            if not math.isclose(float(metric.get("coverage")), coverage, rel_tol=0, abs_tol=1e-9):
                raise ReportingError("metric coverage does not match predictions")
    extra = set(metrics) - set(counts)
    if extra:
        raise ReportingError("metrics contain a tier without predictions")
    return counts


def _prediction_csv_rows(rows, class_names):
    output = []
    for row in rows:
        raw_prediction = int(row["raw"].argmax())
        calibrated_prediction = int(row["calibrated"].argmax())
        output.append(
            {
                "sample_id": row["sample_id"],
                "mapping_tier": row["mapping_tier"],
                "true_label_id": row["true_label"],
                "true_label": class_names[row["true_label"]],
                "raw_prediction_id": raw_prediction,
                "raw_prediction": class_names[raw_prediction],
                "calibrated_prediction_id": calibrated_prediction,
                "calibrated_prediction": class_names[calibrated_prediction],
                "raw_probabilities": json.dumps(row["raw"].tolist()),
                "calibrated_probabilities": json.dumps(row["calibrated"].tolist()),
                "uncalibrated_accepted": row["accepted"]["uncalibrated"],
                "calibrated_accepted": row["accepted"]["calibrated"],
                "calibrated_fixed_rejection_accepted": row["accepted"]["calibrated_fixed_rejection"],
                "calibrated_quality_rejection_accepted": row["accepted"]["calibrated_quality_rejection"],
                "quality_features": json.dumps(
                    row["source"].get("quality_features", {}), sort_keys=True
                ),
            }
        )
    return output


def _protocol_rows(metrics):
    fields = (
        "mapping_tier",
        "variant",
        "sample_count",
        "accepted_count",
        "coverage",
        "selective_accuracy",
        "selective_macro_f1",
        "selective_risk",
    )
    rows = []
    for tier in ("strict", "extended"):
        if tier not in metrics:
            continue
        for variant in VARIANTS:
            metric = metrics[tier][variant]
            rows.append(
                {field: tier if field == "mapping_tier" else variant if field == "variant" else metric.get(field)
                 for field in fields}
            )
    return fields, rows


def _per_class_rows(rows, class_names):
    output = []
    variant = "calibrated_quality_rejection"
    for tier in ("strict", "extended"):
        tier_rows = [row for row in rows if row["mapping_tier"] == tier]
        if not tier_rows:
            continue
        for class_id, class_name in enumerate(class_names):
            selected = [row for row in tier_rows if row["true_label"] == class_id]
            accepted = [row for row in selected if row["accepted"][variant]]
            correct = sum(int(row["calibrated"].argmax()) == class_id for row in accepted)
            output.append(
                {
                    "mapping_tier": tier,
                    "variant": variant,
                    "class_id": class_id,
                    "class_name": class_name,
                    "support": len(selected),
                    "accepted": len(accepted),
                    "correct": correct,
                    "accepted_accuracy": correct / float(len(accepted)) if accepted else None,
                }
            )
    return output


def _risk_coverage_rows(rows):
    output = []
    for tier in ("strict", "extended"):
        tier_rows = [row for row in rows if row["mapping_tier"] == tier]
        if not tier_rows:
            continue
        confidence = np.asarray([row["calibrated"].max() for row in tier_rows])
        correct = np.asarray(
            [int(row["calibrated"].argmax()) == row["true_label"] for row in tier_rows],
            dtype=np.bool_,
        )
        thresholds = sorted(set([0.0, 1.0] + confidence.tolist()), reverse=True)
        for threshold in thresholds:
            accepted = confidence >= threshold
            accepted_count = int(accepted.sum())
            output.append(
                {
                    "mapping_tier": tier,
                    "threshold": float(threshold),
                    "sample_count": len(tier_rows),
                    "accepted_count": accepted_count,
                    "coverage": accepted_count / float(len(tier_rows)),
                    "selective_risk": 1.0 - float(correct[accepted].mean()) if accepted_count else None,
                }
            )
    return output


def _save_confusion(path: Path, rows, class_names):
    tier = "strict" if any(row["mapping_tier"] == "strict" for row in rows) else "extended"
    selected = [
        row for row in rows
        if row["mapping_tier"] == tier and row["accepted"]["calibrated_quality_rejection"]
    ]
    matrix = np.zeros((len(class_names), len(class_names)), dtype=np.int64)
    for row in selected:
        matrix[row["true_label"], int(row["calibrated"].argmax())] += 1
    figure, axis = plt.subplots(figsize=(6, 5))
    image = axis.imshow(matrix, cmap="Blues")
    axis.set_title("{} quality-gated confusion matrix (n={})".format(tier, len(selected)))
    axis.set_xlabel("Predicted")
    axis.set_ylabel("True")
    axis.set_xticks(range(len(class_names)), class_names, rotation=45, ha="right")
    axis.set_yticks(range(len(class_names)), class_names)
    for row_index in range(len(class_names)):
        for column_index in range(len(class_names)):
            axis.text(column_index, row_index, str(matrix[row_index, column_index]), ha="center", va="center")
    figure.colorbar(image, ax=axis)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _save_risk_coverage(path: Path, risk_rows):
    figure, axis = plt.subplots(figsize=(6, 4))
    for tier in ("strict", "extended"):
        selected = [row for row in risk_rows if row["mapping_tier"] == tier and row["selective_risk"] is not None]
        if selected:
            axis.plot(
                [row["coverage"] for row in selected],
                [row["selective_risk"] for row in selected],
                marker="o",
                label=tier,
            )
    axis.set_xlabel("Coverage")
    axis.set_ylabel("Selective risk")
    axis.set_xlim(0, 1.02)
    axis.set_ylim(bottom=0)
    axis.grid(alpha=0.3)
    if axis.lines:
        axis.legend()
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _validated_stress_rows(stress_rows):
    fields = (
        "mapping_tier",
        "variant",
        "degradation",
        "level",
        "sample_count",
        "macro_f1",
        "coverage",
    )
    output = []
    for row in stress_rows:
        if not isinstance(row, Mapping) or any(field not in row for field in fields):
            raise ReportingError("stress rows must contain the reporting schema")
        output.append({field: row[field] for field in fields})
    return fields, output


def _save_stress(path: Path, rows):
    figure, axis = plt.subplots(figsize=(7, 4))
    series = {}
    for row in rows:
        key = (row["mapping_tier"], row["variant"], row["degradation"])
        series.setdefault(key, []).append(row)
    for key, values in sorted(series.items()):
        values.sort(key=lambda row: int(row["level"]))
        axis.plot(
            [row["level"] for row in values],
            [row["macro_f1"] for row in values],
            marker="o",
            label="/".join(key),
        )
    axis.set_xlabel("Stress level")
    axis.set_ylabel("Macro-F1")
    axis.set_ylim(0, 1.02)
    axis.grid(alpha=0.3)
    if series:
        axis.legend(fontsize=7)
    else:
        axis.text(0.5, 0.5, "No stress experiment results", ha="center", va="center", transform=axis.transAxes)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _summary_markdown(protocol, metrics, counts) -> str:
    lines = [
        "# CVB → CBVD-5 跨域牛只行为鲁棒性结果",
        "",
        "状态：`complete`（报告生成完成，不等同于达到生产部署门槛）。",
        "",
        "## 冻结协议",
        "",
        "- 外部测试集：{} {}。".format(protocol.get("dataset_id", "unknown"), protocol.get("dataset_version", "unknown")),
        "- 模型哈希：`{}`。".format(str(protocol.get("checkpoint_sha256", ""))[:12]),
        "- 外部测试标签只用于最终计分，不用于校准、阈值或质量门训练。",
        "",
        "## 结果摘要",
        "",
    ]
    for tier in ("strict", "extended"):
        if tier not in counts:
            continue
        lines.append("### {} 映射（n={}）".format(tier, counts[tier]))
        lines.append("")
        lines.append("| 协议 | 样本数 | 接受数 | 覆盖率 | 选择性风险 | Macro-F1 |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for variant in VARIANTS:
            row = metrics[tier][variant]
            lines.append(
                "| {} | {} | {} | {} | {} | {} |".format(
                    variant,
                    row.get("sample_count"),
                    row.get("accepted_count"),
                    row.get("coverage"),
                    row.get("selective_risk"),
                    row.get("selective_macro_f1"),
                )
            )
        lines.append("")
    lines.extend(
        [
            "## 结论边界",
            "",
            "- 本实验支持对公开外部测试集上的行为识别跨域鲁棒性进行描述。",
            "- 当前证据不支持疾病诊断、核心体温测量、真实牧场长期稳定性或无人值守生产部署声明。",
            "- 拒识改善必须同时报告覆盖率，不能只展示被接受样本的准确率。",
            "- 每项指标旁保留外部样本数；小样本类别只作探索性结果。",
            "",
        ]
    )
    return "\n".join(lines)


def write_cross_domain_report(
    output_root,
    *,
    protocol: Mapping[str, object],
    evaluation: Mapping[str, object],
    stress_rows: Iterable[Mapping[str, object]],
    class_names: Sequence[str],
) -> dict:
    """Write the complete auditable report bundle and return its compact summary."""

    if not isinstance(protocol, Mapping):
        raise ReportingError("protocol must be a mapping")
    if not isinstance(evaluation, Mapping):
        raise ReportingError("evaluation must be a mapping")
    rows = _validated_predictions(evaluation.get("predictions", ()), class_names)
    metrics = evaluation.get("metrics")
    if not isinstance(metrics, Mapping):
        raise ReportingError("evaluation metrics must be a mapping")
    counts = _validate_metric_counts(metrics, rows)
    output = Path(output_root)
    output.mkdir(parents=True, exist_ok=True)

    prediction_fields = (
        "sample_id", "mapping_tier", "true_label_id", "true_label",
        "raw_prediction_id", "raw_prediction", "calibrated_prediction_id",
        "calibrated_prediction", "raw_probabilities", "calibrated_probabilities",
        "uncalibrated_accepted", "calibrated_accepted",
        "calibrated_fixed_rejection_accepted",
        "calibrated_quality_rejection_accepted", "quality_features",
    )
    _write_csv(output / "predictions.csv", prediction_fields, _prediction_csv_rows(rows, class_names))
    protocol_fields, protocol_rows = _protocol_rows(metrics)
    _write_csv(output / "protocol_comparison.csv", protocol_fields, protocol_rows)
    per_class = _per_class_rows(rows, class_names)
    _write_csv(
        output / "per_class_metrics.csv",
        ("mapping_tier", "variant", "class_id", "class_name", "support", "accepted", "correct", "accepted_accuracy"),
        per_class,
    )
    risk_rows = _risk_coverage_rows(rows)
    _write_csv(
        output / "risk_coverage.csv",
        ("mapping_tier", "threshold", "sample_count", "accepted_count", "coverage", "selective_risk"),
        risk_rows,
    )
    stress_fields, validated_stress = _validated_stress_rows(stress_rows)
    _write_csv(output / "stress_metrics.csv", stress_fields, validated_stress)
    _save_confusion(output / "confusion_matrix.png", rows, class_names)
    _save_risk_coverage(output / "risk_coverage.png", risk_rows)
    _save_stress(output / "stress_curves.png", validated_stress)
    summary = {
        "status": "complete",
        "dataset_id": protocol.get("dataset_id"),
        "dataset_version": protocol.get("dataset_version"),
        "sample_counts": counts,
        "checkpoint_sha256": protocol.get("checkpoint_sha256"),
        "metrics": metrics,
        "claim_boundaries": [
            "behavior recognition robustness only",
            "not disease diagnosis",
            "not unattended production deployment evidence",
        ],
    }
    _write_json(
        output / "metrics.json",
        {
            "status": "complete",
            "protocol": dict(protocol),
            "sample_counts": counts,
            "metrics": metrics,
            "claim_boundaries": summary["claim_boundaries"],
        },
    )
    (output / "summary.md").write_text(
        _summary_markdown(protocol, metrics, counts), encoding="utf-8"
    )
    return summary

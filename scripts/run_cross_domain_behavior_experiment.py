"""Validate and execute the frozen CVB-to-external behavior protocol."""

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import shutil
import time

import numpy as np
import torch

from cattle_health_app.behavior.cross_domain_experiment import (
    ExternalPrediction,
    ProtocolViolation,
    evaluate_variants,
    freeze_heuristic_quality_gate,
    load_frozen_protocol,
)
from cattle_health_app.behavior.cross_domain_reporting import write_cross_domain_report
from cattle_health_app.behavior.cvb_labels import CVB_NAME_TO_ID
from cattle_health_app.behavior.degradations import DEGRADATION_NAMES, apply_degradation
from cattle_health_app.behavior.external_inference import (
    FrozenX3DLogitPredictor,
    collect_external_predictions_reusing_physical_clips,
)
from cattle_health_app.behavior.external_video_dataset import load_external_samples
from cattle_health_app.behavior.model import LABEL_ORDER


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
    except OSError as exc:
        raise ProtocolViolation("could not hash experiment input: {}".format(exc)) from exc
    return digest.hexdigest()


def _validate_manifest(path: Path):
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or not {
                "sample_id",
                "split",
                "mapping_tier",
                "mapped_label",
            }.issubset(reader.fieldnames):
                raise ProtocolViolation(
                    "manifest must contain sample_id, split, mapping_tier, and mapped_label"
                )
            count = 0
            sample_ids = set()
            tiers = set()
            class_counts = {}
            for row in reader:
                sample_id = row.get("sample_id", "").strip()
                if not sample_id or sample_id in sample_ids:
                    raise ProtocolViolation("manifest sample_id values must be unique and non-empty")
                if row.get("split") != "test":
                    raise ProtocolViolation("external manifest must be test-only")
                tier = row.get("mapping_tier")
                if tier not in {"strict", "extended"}:
                    raise ProtocolViolation("mapping_tier must be strict or extended")
                tiers.add(tier)
                mapped_label = row.get("mapped_label")
                if mapped_label not in LABEL_ORDER:
                    raise ProtocolViolation(
                        "mapped_label must belong to the frozen CVB label order"
                    )
                class_counts[mapped_label] = class_counts.get(mapped_label, 0) + 1
                sample_ids.add(sample_id)
                count += 1
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ProtocolViolation("could not validate external manifest: {}".format(exc)) from exc
    if count == 0:
        raise ProtocolViolation("external manifest must contain at least one sample")
    if len(tiers) != 1:
        raise ProtocolViolation("each manifest must contain exactly one mapping_tier")
    return count, tiers.pop(), dict(sorted(class_counts.items()))


def _parse_levels(raw: str):
    try:
        levels = tuple(int(value.strip()) for value in raw.split(","))
    except (TypeError, ValueError) as exc:
        raise ProtocolViolation("stress levels must be comma-separated integers") from exc
    if not levels or any(level not in {0, 1, 2, 3} for level in levels):
        raise ProtocolViolation("stress levels must be selected from 0,1,2,3")
    if len(set(levels)) != len(levels):
        raise ProtocolViolation("stress levels must not contain duplicates")
    return levels


def _write_json_atomic(path: Path, payload) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _protocol_fingerprint(protocol) -> str:
    payload = json.dumps(
        protocol, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _canonical_sha256(payload) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sample_set_sha256(samples) -> str:
    rows = [
        {
            "mapping_tier": sample.mapping_tier,
            "sample_id": sample.sample_id,
            "source_video_path": sample.source_video_path,
            "source_sha256": sample.source_sha256,
            "start_second": float(sample.start_second),
            "end_second": float(sample.end_second),
            "crop_box": [float(value) for value in sample.crop_box],
            "mapped_label": sample.mapped_label,
        }
        for sample in samples
    ]
    rows.sort(key=lambda row: (row["mapping_tier"], row["sample_id"]))
    return _canonical_sha256(rows)


def _physical_clip_count(samples) -> int:
    return len(
        {
            (
                sample.sample_id,
                sample.source_video_path,
                float(sample.start_second),
                float(sample.end_second),
                tuple(float(value) for value in sample.crop_box),
                sample.mapped_label,
            )
            for sample in samples
        }
    )


def _synchronize_device(device: str) -> None:
    if str(device).startswith("cuda"):
        torch.cuda.synchronize()


def _load_inference_timing(path: Path, protocol_fingerprint: str) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProtocolViolation("inference timing artifact is unreadable") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != 1
        or payload.get("protocol_fingerprint") != protocol_fingerprint
        or not isinstance(payload.get("stress"), list)
    ):
        raise ProtocolViolation("inference timing does not match frozen protocol")
    return payload


def _timing_record(*, elapsed, samples, device, cache_identity) -> dict:
    logical_count = len(samples)
    physical_count = _physical_clip_count(samples)
    return {
        **dict(cache_identity),
        "wall_seconds": float(elapsed),
        "logical_sample_count": logical_count,
        "physical_clip_count": physical_count,
        "logical_samples_per_second": logical_count / float(elapsed),
        "physical_clips_per_second": physical_count / float(elapsed),
        "device": str(device),
        "scope": "decode_transform_model_forward_and_quality_measurement",
    }


def _prediction_to_dict(row: ExternalPrediction) -> dict:
    return {
        "sample_id": row.sample_id,
        "mapping_tier": row.mapping_tier,
        "true_label": int(row.true_label),
        "logits": [float(value) for value in row.logits],
        "quality_features": {
            key: float(value) for key, value in row.quality_features.items()
        },
    }


def _prediction_from_dict(payload) -> ExternalPrediction:
    if not isinstance(payload, dict):
        raise ProtocolViolation("prediction cache row must be an object")
    try:
        return ExternalPrediction(
            sample_id=payload["sample_id"],
            mapping_tier=payload["mapping_tier"],
            true_label=payload["true_label"],
            logits=tuple(payload["logits"]),
            quality_features=payload["quality_features"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ProtocolViolation("prediction cache row is invalid") from exc


def _write_prediction_cache(
    path: Path,
    protocol_fingerprint: str,
    predictions,
    transformations=(),
    *,
    cache_identity,
    sample_set_sha256: str,
) -> None:
    transformation_rows = list(transformations)
    _write_json_atomic(
        path,
        {
            "schema_version": 1,
            "protocol_fingerprint": protocol_fingerprint,
            "cache_identity": dict(cache_identity),
            "sample_set_sha256": sample_set_sha256,
            "predictions": [_prediction_to_dict(row) for row in predictions],
            "transformations": transformation_rows,
            "transformation_sha256": _canonical_sha256(transformation_rows),
        },
    )


def _load_prediction_cache(
    path: Path,
    protocol_fingerprint: str,
    *,
    expected_cache_identity,
    expected_sample_set_sha256: str,
    expected_transformation_sample_ids=None,
):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProtocolViolation("prediction cache is unreadable") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != 1
        or payload.get("protocol_fingerprint") != protocol_fingerprint
        or not isinstance(payload.get("predictions"), list)
        or not isinstance(payload.get("transformations"), list)
    ):
        raise ProtocolViolation("prediction cache does not match the frozen protocol")
    if payload.get("cache_identity") != dict(expected_cache_identity):
        raise ProtocolViolation("prediction cache condition does not match")
    if payload.get("sample_set_sha256") != expected_sample_set_sha256:
        raise ProtocolViolation("prediction cache sample set does not match")
    if payload.get("transformation_sha256") != _canonical_sha256(
        payload["transformations"]
    ):
        raise ProtocolViolation("prediction cache transformation evidence is invalid")
    if expected_cache_identity.get("kind") == "stress":
        degradation = expected_cache_identity.get("degradation")
        level = expected_cache_identity.get("level")
        if not payload["transformations"] or any(
            not isinstance(row, dict)
            or row.get("name") != degradation
            or row.get("level") != level
            for row in payload["transformations"]
        ):
            raise ProtocolViolation("prediction cache condition transformations do not match")
        if expected_transformation_sample_ids is not None:
            recorded_ids = sorted(
                row.get("sample_id") for row in payload["transformations"]
            )
            if recorded_ids != sorted(expected_transformation_sample_ids):
                raise ProtocolViolation(
                    "prediction cache transformation sample set does not match"
                )
    return tuple(_prediction_from_dict(row) for row in payload["predictions"])


def _validate_prediction_alignment(predictions, samples) -> None:
    prediction_rows = tuple(predictions)
    sample_rows = tuple(samples)
    expected = {
        (sample.mapping_tier, sample.sample_id): CVB_NAME_TO_ID[sample.mapped_label] - 1
        for sample in sample_rows
    }
    actual = {
        (row.mapping_tier, row.sample_id): int(row.true_label)
        for row in prediction_rows
    }
    if len(expected) != len(sample_rows) or len(actual) != len(prediction_rows) or actual != expected:
        raise ProtocolViolation(
            "prediction cache must stay exactly aligned with frozen manifest samples"
        )


def _select_stress_samples(samples, per_class: int, seed: int):
    selected = []
    grouped = {}
    for sample in samples:
        grouped.setdefault((sample.mapping_tier, sample.mapped_label), []).append(sample)
    for key in sorted(grouped):
        by_source_group = {}
        for sample in grouped[key]:
            by_source_group.setdefault(sample.source_group_id, []).append(sample)
        ordered_groups = sorted(
            by_source_group,
            key=lambda group_id: hashlib.sha256(
                "{}:{}:{}:{}".format(seed, key[0], key[1], group_id).encode(
                    "utf-8"
                )
            ).hexdigest(),
        )
        candidates = []
        maximum_group_size = max(len(rows) for rows in by_source_group.values())
        for round_index in range(maximum_group_size):
            for group_id in ordered_groups:
                rows = sorted(
                    by_source_group[group_id],
                    key=lambda row: hashlib.sha256(
                        "{}:{}".format(seed, row.sample_id).encode("utf-8")
                    ).hexdigest(),
                )
                if round_index < len(rows):
                    candidates.append(rows[round_index])
        selected.extend(candidates[:per_class])
    return tuple(selected)


def _stable_transform_seed(seed: int, sample_id: str, name: str, level: int) -> int:
    payload = "{}:{}:{}:{}".format(seed, sample_id, name, level).encode("utf-8")
    return int(hashlib.sha256(payload).hexdigest()[:8], 16)


def _stress_metric_rows(evaluation, name: str, level: int):
    rows = []
    for tier in ("strict", "extended"):
        if tier not in evaluation["metrics"]:
            continue
        for variant in ("calibrated", "calibrated_quality_rejection"):
            metric = evaluation["metrics"][tier][variant]
            rows.append(
                {
                    "mapping_tier": tier,
                    "variant": variant,
                    "degradation": name,
                    "level": level,
                    "sample_count": metric["sample_count"],
                    "macro_f1": metric["selective_macro_f1"],
                    "coverage": metric["coverage"],
                }
            )
    return rows


def _few_shot_gate(samples, evaluation) -> dict:
    strict_metric = evaluation["metrics"].get("strict", {}).get("calibrated", {})
    macro_f1 = strict_metric.get("selective_macro_f1")
    groups = {}
    for sample in samples:
        if sample.mapping_tier == "strict":
            groups.setdefault(sample.mapped_label, set()).add(sample.source_group_id)
    group_counts = {key: len(value) for key, value in sorted(groups.items())}
    enough_groups = bool(group_counts) and all(count >= 5 for count in group_counts.values())
    low_zero_shot = isinstance(macro_f1, (int, float)) and math.isfinite(
        float(macro_f1)
    ) and float(macro_f1) < 0.30
    decision = "go_separate_adaptation_plan" if low_zero_shot and enough_groups else "no_go"
    reasons = []
    if not low_zero_shot:
        reasons.append("strict calibrated zero-shot Macro-F1 is not below 0.30")
    if not enough_groups:
        reasons.append(
            "at least one strict class has fewer than five source groups before reserving one final-test group"
        )
    return {
        "decision": decision,
        "strict_calibrated_zero_shot_macro_f1": macro_f1,
        "source_group_counts": group_counts,
        "required_total_groups_per_class": 5,
        "reasons": reasons,
        "adaptation_executed": False,
    }


def _write_protocol(output: Path, payload: dict, resume: bool) -> None:
    output.mkdir(parents=True, exist_ok=True)
    path = output / "protocol.json"
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ProtocolViolation("existing protocol.json is unreadable: {}".format(exc)) from exc
        if existing != payload:
            raise ProtocolViolation("existing output protocol differs from frozen inputs")
        if not resume:
            raise ProtocolViolation("matching output exists; pass --resume to reuse it")
        return
    unexpected = [
        item for item in output.iterdir() if item.name != "audit" or not item.is_dir()
    ]
    if unexpected:
        raise ProtocolViolation("output directory is non-empty without protocol.json")
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", action="append", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--calibration", required=True)
    parser.add_argument(
        "--project-root", default=str(Path(__file__).resolve().parents[1])
    )
    parser.add_argument("--seed", type=int, default=20260823)
    parser.add_argument("--stress-levels", default="0,1,2,3")
    parser.add_argument("--stress-per-class", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    project_root = Path(args.project_root).expanduser().resolve()
    manifests = tuple(Path(value).expanduser().resolve() for value in args.manifest)
    output = Path(args.output).expanduser().resolve()
    try:
        output.relative_to(project_root)
    except ValueError as exc:
        raise ProtocolViolation("output must stay inside project_root") from exc
    checkpoint = Path(args.checkpoint).expanduser().resolve()
    calibration = Path(args.calibration).expanduser().resolve()
    if isinstance(args.seed, bool):
        raise ProtocolViolation("seed must be an integer")
    if (
        isinstance(args.batch_size, bool)
        or args.batch_size <= 0
        or isinstance(args.stress_per_class, bool)
        or args.stress_per_class <= 0
    ):
        raise ProtocolViolation("batch-size and stress-per-class must be positive integers")
    manifest_rows = []
    for manifest in manifests:
        count, tier, class_counts = _validate_manifest(manifest)
        manifest_rows.append(
            {
                "mapping_tier": tier,
                "path": str(manifest),
                "sha256": _sha256_file(manifest),
                "sample_count": count,
                "class_counts": class_counts,
            }
        )
    tiers = [row["mapping_tier"] for row in manifest_rows]
    if len(set(tiers)) != len(tiers):
        raise ProtocolViolation("mapping_tier manifests must not be duplicated")
    if not args.dry_run and set(tiers) != {"strict", "extended"}:
        raise ProtocolViolation("formal experiment requires strict and extended manifests")
    manifest_rows.sort(key=lambda row: row["mapping_tier"])
    sample_counts = {
        row["mapping_tier"]: row["sample_count"] for row in manifest_rows
    }
    manifest_hashes = {
        row["mapping_tier"]: row["sha256"] for row in manifest_rows
    }
    external_class_counts = {
        row["mapping_tier"]: row["class_counts"] for row in manifest_rows
    }
    combined_manifest_hash = hashlib.sha256(
        json.dumps(manifest_hashes, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    frozen = load_frozen_protocol(checkpoint, calibration)
    levels = _parse_levels(args.stress_levels)
    if str(args.device).startswith("cuda") and not torch.cuda.is_available():
        raise ProtocolViolation("CUDA device requested but torch.cuda.is_available() is false")
    output_parent = output.parent if output.parent.exists() else project_root
    free_bytes = shutil.disk_usage(output_parent).free
    protocol = {
        "schema_version": 1,
        "checkpoint_sha256": frozen.checkpoint_sha256,
        "calibration_sha256": frozen.calibration_sha256,
        "validation_manifest_sha256": frozen.validation_manifest_sha256,
        "manifest_sha256": combined_manifest_hash,
        "manifest_sha256s": manifest_hashes,
        "manifests": manifest_rows,
        "external_sample_count": sum(sample_counts.values()),
        "external_sample_counts": sample_counts,
        "external_class_counts": external_class_counts,
        "temperature": frozen.temperature,
        "fixed_min_confidence": frozen.fixed_min_confidence,
        "fixed_max_normalized_entropy": frozen.fixed_max_normalized_entropy,
        "seed": args.seed,
        "stress_levels": list(levels),
        "device": args.device,
        "batch_size": args.batch_size,
        "stress_per_class": args.stress_per_class,
        "stress_degradations": list(DEGRADATION_NAMES),
        "dataset_id": "cbvd5",
        "dataset_version": "kaggle-version-11",
        "quality_gate_policy": "predeclared_heuristic",
        "quality_gate_combines_fixed_rejection": False,
        "stress_selection_policy": "seeded_source_group_round_robin",
        "metric_definitions": {
            "macro_f1": "unweighted_over_target_classes_present_in_mapping_tier",
            "nll": "mean_negative_log_target_probability",
            "ece": "15_equal_width_bins_top_label_confidence",
            "brier": "mean_sum_squared_error_over_12_class_probability_vector",
            "inference_timing": "decode_transform_model_forward_and_quality_measurement",
        },
    }
    _write_protocol(output, protocol, args.resume)
    _write_json_atomic(
        output / "preflight.json",
        {
            "status": (
                "validated_not_run" if args.dry_run else "validated_pending_inference"
            ),
            "available_disk_bytes": free_bytes,
            "cuda_available": bool(torch.cuda.is_available()),
            "requested_device": args.device,
        },
    )
    print(json.dumps(protocol, ensure_ascii=False, sort_keys=True))
    if args.dry_run:
        return 0

    gate = freeze_heuristic_quality_gate(
        checkpoint_sha256=frozen.checkpoint_sha256,
        frozen_before_manifest_sha256=combined_manifest_hash,
    )
    gate_path = output / "quality_gate.json"
    gate_payload = gate.to_dict()
    if gate_path.is_file():
        try:
            existing_gate = json.loads(gate_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ProtocolViolation("existing quality gate is unreadable") from exc
        if existing_gate != gate_payload:
            raise ProtocolViolation("existing quality gate differs from frozen rules")
    else:
        _write_json_atomic(gate_path, gate_payload)

    samples = []
    for row in manifest_rows:
        loaded = load_external_samples(row["path"], project_root)
        if len(loaded) != row["sample_count"] or any(
            sample.mapping_tier != row["mapping_tier"] for sample in loaded
        ):
            raise ProtocolViolation("loaded samples do not match the frozen manifest")
        samples.extend(loaded)
    samples = tuple(samples)
    _write_json_atomic(
        output / "run_state.json",
        {
            "status": "running",
            "protocol_fingerprint": _protocol_fingerprint(protocol),
        },
    )
    predictor = FrozenX3DLogitPredictor(checkpoint, device=args.device)
    fingerprint = _protocol_fingerprint(protocol)
    timing_path = output / "inference_timing.json"
    if args.resume and timing_path.is_file():
        inference_timing = _load_inference_timing(timing_path, fingerprint)
    else:
        inference_timing = {
            "schema_version": 1,
            "protocol_fingerprint": fingerprint,
            "stress": [],
        }
    baseline_sample_set_sha256 = _sample_set_sha256(samples)
    baseline_cache = output / "baseline_raw_predictions.json"
    if args.resume and baseline_cache.is_file():
        baseline_predictions = _load_prediction_cache(
            baseline_cache,
            fingerprint,
            expected_cache_identity={"kind": "baseline"},
            expected_sample_set_sha256=baseline_sample_set_sha256,
        )
        if not isinstance(inference_timing.get("baseline"), dict):
            raise ProtocolViolation(
                "baseline cache exists without matching inference timing"
            )
    else:
        _synchronize_device(args.device)
        started = time.perf_counter()
        baseline_predictions = collect_external_predictions_reusing_physical_clips(
            samples,
            project_root,
            predictor=predictor,
            batch_size=args.batch_size,
            progress=lambda completed, total: print(
                "baseline inference: {}/{} physical clips".format(completed, total),
                flush=True,
            ),
        )
        _synchronize_device(args.device)
        elapsed = max(time.perf_counter() - started, np.finfo(np.float64).eps)
        _write_prediction_cache(
            baseline_cache,
            fingerprint,
            baseline_predictions,
            cache_identity={"kind": "baseline"},
            sample_set_sha256=baseline_sample_set_sha256,
        )
        inference_timing["baseline"] = _timing_record(
            elapsed=elapsed,
            samples=samples,
            device=args.device,
            cache_identity={"kind": "baseline"},
        )
        _write_json_atomic(timing_path, inference_timing)
    _validate_prediction_alignment(baseline_predictions, samples)
    evaluation = evaluate_variants(
        baseline_predictions,
        temperature=frozen.temperature,
        fixed_min_confidence=frozen.fixed_min_confidence,
        fixed_max_normalized_entropy=frozen.fixed_max_normalized_entropy,
        quality_gate=gate,
        checkpoint_sha256=frozen.checkpoint_sha256,
    )

    stress_samples = _select_stress_samples(
        samples, args.stress_per_class, args.seed
    )
    stress_sample_set_sha256 = _sample_set_sha256(stress_samples)
    stress_physical_sample_ids = sorted(
        {sample.sample_id for sample in stress_samples}
    )
    _write_json_atomic(
        output / "stress_selection.json",
        {
            "schema_version": 1,
            "policy": "seeded_source_group_round_robin",
            "seed": args.seed,
            "per_class": args.stress_per_class,
            "sample_set_sha256": stress_sample_set_sha256,
            "logical_sample_count": len(stress_samples),
            "physical_clip_count": _physical_clip_count(stress_samples),
            "samples": [
                {
                    "mapping_tier": sample.mapping_tier,
                    "sample_id": sample.sample_id,
                    "source_group_id": sample.source_group_id,
                    "mapped_label": sample.mapped_label,
                }
                for sample in stress_samples
            ],
        },
    )
    baseline_by_key = {
        (row.mapping_tier, row.sample_id): row for row in baseline_predictions
    }
    stress_baseline = tuple(
        baseline_by_key[(sample.mapping_tier, sample.sample_id)]
        for sample in stress_samples
    )
    stress_rows = []
    stress_root = output / "stress"
    stress_root.mkdir(exist_ok=True)
    for name in DEGRADATION_NAMES:
        for level in levels:
            if level == 0:
                stress_predictions = stress_baseline
            else:
                cache_path = stress_root / "{}_level_{}.json".format(name, level)
                cache_identity = {
                    "kind": "stress",
                    "degradation": name,
                    "level": level,
                }
                if args.resume and cache_path.is_file():
                    stress_predictions = _load_prediction_cache(
                        cache_path,
                        fingerprint,
                        expected_cache_identity=cache_identity,
                        expected_sample_set_sha256=stress_sample_set_sha256,
                        expected_transformation_sample_ids=stress_physical_sample_ids,
                    )
                    if not any(
                        row.get("kind") == "stress"
                        and row.get("degradation") == name
                        and row.get("level") == level
                        for row in inference_timing["stress"]
                        if isinstance(row, dict)
                    ):
                        raise ProtocolViolation(
                            "stress cache exists without matching inference timing"
                        )
                else:
                    transformations = []

                    def transform(frames, sample, degradation=name, severity=level):
                        transform_seed = _stable_transform_seed(
                            args.seed, sample.sample_id, degradation, severity
                        )
                        transformed, record = apply_degradation(
                            frames,
                            name=degradation,
                            level=severity,
                            seed=transform_seed,
                        )
                        transformations.append(
                            {
                                "sample_id": sample.sample_id,
                                "mapping_tier_used_for_decode": sample.mapping_tier,
                                **record.to_dict(),
                            }
                        )
                        return transformed

                    _synchronize_device(args.device)
                    started = time.perf_counter()
                    stress_predictions = (
                        collect_external_predictions_reusing_physical_clips(
                            stress_samples,
                            project_root,
                            predictor=predictor,
                            batch_size=args.batch_size,
                            frame_transform=transform,
                            progress=lambda completed, total, n=name, value=level: print(
                                "stress {} level {}: {}/{} physical clips".format(
                                    n, value, completed, total
                                ),
                                flush=True,
                            ),
                        )
                    )
                    _synchronize_device(args.device)
                    elapsed = max(
                        time.perf_counter() - started, np.finfo(np.float64).eps
                    )
                    _write_prediction_cache(
                        cache_path,
                        fingerprint,
                        stress_predictions,
                        transformations,
                        cache_identity=cache_identity,
                        sample_set_sha256=stress_sample_set_sha256,
                    )
                    inference_timing["stress"].append(
                        _timing_record(
                            elapsed=elapsed,
                            samples=stress_samples,
                            device=args.device,
                            cache_identity=cache_identity,
                        )
                    )
                    _write_json_atomic(timing_path, inference_timing)
            _validate_prediction_alignment(stress_predictions, stress_samples)
            stress_evaluation = evaluate_variants(
                stress_predictions,
                temperature=frozen.temperature,
                fixed_min_confidence=frozen.fixed_min_confidence,
                fixed_max_normalized_entropy=frozen.fixed_max_normalized_entropy,
                quality_gate=gate,
                checkpoint_sha256=frozen.checkpoint_sha256,
            )
            stress_rows.extend(_stress_metric_rows(stress_evaluation, name, level))

    few_shot = _few_shot_gate(samples, evaluation)
    _write_json_atomic(output / "few_shot_gate.json", few_shot)
    summary = write_cross_domain_report(
        output,
        protocol=protocol,
        evaluation=evaluation,
        stress_rows=stress_rows,
        class_names=LABEL_ORDER,
        inference_timing=inference_timing,
    )
    _write_json_atomic(
        output / "run_state.json",
        {
            "status": "complete",
            "protocol_fingerprint": fingerprint,
            "external_sample_count": len(baseline_predictions),
            "stress_sample_count": len(stress_samples),
            "stress_sample_set_sha256": stress_sample_set_sha256,
            "stress_result_rows": len(stress_rows),
            "few_shot_decision": few_shot["decision"],
            "report_status": summary["status"],
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

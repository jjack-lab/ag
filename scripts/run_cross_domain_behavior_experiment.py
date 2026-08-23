"""Validate and execute the frozen CVB-to-external behavior protocol."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

from cattle_health_app.behavior.cross_domain_experiment import (
    ProtocolViolation,
    load_frozen_protocol,
)


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


def _validate_manifest(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or not {"sample_id", "split"}.issubset(reader.fieldnames):
                raise ProtocolViolation("manifest must contain sample_id and split")
            count = 0
            sample_ids = set()
            for row in reader:
                sample_id = row.get("sample_id", "").strip()
                if not sample_id or sample_id in sample_ids:
                    raise ProtocolViolation("manifest sample_id values must be unique and non-empty")
                if row.get("split") != "test":
                    raise ProtocolViolation("external manifest must be test-only")
                sample_ids.add(sample_id)
                count += 1
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ProtocolViolation("could not validate external manifest: {}".format(exc)) from exc
    if count == 0:
        raise ProtocolViolation("external manifest must contain at least one sample")
    return count


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
    if any(output.iterdir()):
        raise ProtocolViolation("output directory is non-empty without protocol.json")
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--calibration", required=True)
    parser.add_argument("--seed", type=int, default=20260823)
    parser.add_argument("--stress-levels", default="0,1,2,3")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    manifest = Path(args.manifest).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    checkpoint = Path(args.checkpoint).expanduser().resolve()
    calibration = Path(args.calibration).expanduser().resolve()
    if isinstance(args.seed, bool):
        raise ProtocolViolation("seed must be an integer")
    sample_count = _validate_manifest(manifest)
    frozen = load_frozen_protocol(checkpoint, calibration)
    levels = _parse_levels(args.stress_levels)
    protocol = {
        "schema_version": 1,
        "status": "validated_not_run" if args.dry_run else "validated_pending_inference",
        "checkpoint_sha256": frozen.checkpoint_sha256,
        "calibration_sha256": frozen.calibration_sha256,
        "validation_manifest_sha256": frozen.validation_manifest_sha256,
        "manifest_sha256": _sha256_file(manifest),
        "external_sample_count": sample_count,
        "temperature": frozen.temperature,
        "fixed_min_confidence": frozen.fixed_min_confidence,
        "fixed_max_normalized_entropy": frozen.fixed_max_normalized_entropy,
        "seed": args.seed,
        "stress_levels": list(levels),
        "device": args.device,
    }
    _write_protocol(output, protocol, args.resume)
    print(json.dumps(protocol, ensure_ascii=False, sort_keys=True))
    if not args.dry_run:
        raise ProtocolViolation(
            "validated protocol is ready; external inference is executed in Task 12 after quality-gate fitting"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

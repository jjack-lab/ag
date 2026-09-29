"""Rebuild or validate the exact frozen WAID4500 dataset."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cattle_health_app.detection.waid_repro import (  # noqa: E402
    rebuild_dataset,
    validate_dataset,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=PROJECT_ROOT / "data" / "external" / "waid" / "raw",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=PROJECT_ROOT / "reproducibility" / "waid4500" / "dataset_manifest.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            PROJECT_ROOT
            / "data"
            / "external"
            / "waid"
            / "derived"
            / "waid4500_v1"
        ),
    )
    parser.add_argument("--expected-train", type=int, default=4500)
    parser.add_argument("--expected-valid", type=int, default=200)
    parser.add_argument("--expected-test", type=int, default=20)
    parser.add_argument("--validate-only", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    expected = {
        "train": args.expected_train,
        "valid": args.expected_valid,
        "test": args.expected_test,
    }
    try:
        operation = validate_dataset if args.validate_only else rebuild_dataset
        summary = operation(args.raw_root, args.manifest, args.output, expected)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0
    except KeyboardInterrupt:
        print("[ERROR] interrupted", file=sys.stderr)
        return 130
    except Exception as exc:
        print("[ERROR] {}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

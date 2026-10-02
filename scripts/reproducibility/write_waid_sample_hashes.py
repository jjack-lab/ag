"""Record per-sample content hashes for the frozen WAID4500 dataset."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cattle_health_app.detection.waid_repro import write_sample_hashes  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.project_root.expanduser().resolve()
    dataset = args.dataset or root / "data/external/waid/derived/waid4500_v1"
    manifest = args.manifest or root / "reproducibility/waid4500/dataset_manifest.csv"
    output = args.output or root / "reproducibility/waid4500/dataset_samples.sha256"
    try:
        destination = write_sample_hashes(dataset, manifest, output)
    except KeyboardInterrupt:
        print("[ERROR] interrupted", file=sys.stderr)
        return 130
    except Exception as exc:
        print("[ERROR] {}".format(exc), file=sys.stderr)
        return 1
    print(str(destination))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Import the local WAID data and archived YOLO11s training assets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cattle_health_app.detection.waid_repro import ImportSources, import_assets  # noqa: E402


RUN_NAME = "waid4500_v1_yolo11s_img960_e120"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-raw",
        type=Path,
        default=Path(r"E:\大创\WAID-main\WAID"),
        help="Original WAID root; override this path on another computer.",
    )
    parser.add_argument(
        "--source-training-root",
        type=Path,
        default=Path(r"E:\大创\WAID_YOLO11"),
        help="Old training project root; override this path on another computer.",
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--replace", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    training = args.source_training_root
    sources = ImportSources(
        raw=args.source_raw,
        frozen_dataset=training / "waid4500_v1",
        pretrained=training / "yolo11s.pt",
        run=training / "runs" / RUN_NAME,
        logs=training / "training_logs",
    )
    try:
        report = import_assets(sources, args.project_root, replace=args.replace)
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except KeyboardInterrupt:
        print("[ERROR] interrupted", file=sys.stderr)
        return 130
    except Exception as exc:
        print("[ERROR] {}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

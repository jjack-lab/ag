"""Check or run the portable WAID4500 YOLO11s training protocol."""

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
    check_training_runtime,
    load_training_config,
    run_training,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--device")
    parser.add_argument("--resume", type=Path)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.project_root.expanduser().resolve()
    config_path = args.config
    if config_path is None:
        config_path = root / "reproducibility" / "waid4500" / "training_config.yaml"
    try:
        config = load_training_config(config_path, root)
        if args.device is not None:
            config["device"] = args.device
        if args.check_only:
            report = check_training_runtime(config)
            print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        result = run_training(config, args.smoke, args.device, args.resume)
        print(json.dumps({"status": "complete", "save_dir": str(result.save_dir)}))
        return 0
    except KeyboardInterrupt:
        print("[ERROR] interrupted", file=sys.stderr)
        return 130
    except Exception as exc:
        print("[ERROR] {}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

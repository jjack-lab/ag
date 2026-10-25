"""检查一次现场验收交付包是否齐全。

用法：
    python scripts/check_field_acceptance.py --root data/field_acceptance/2026-10-27
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cattle_health_app.field_acceptance import check_field_acceptance


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验现场验收包是否齐全、哈希是否对得上")
    parser.add_argument("--root", required=True, help="验收包目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON 而不是文本摘要")
    args = parser.parse_args(argv)

    result = check_field_acceptance(args.root)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        summary = result["summary"]
        print(f"验收包：{result['root']}")
        print(f"视频 {summary['clips']} 段 / 台账 {summary['ledger_rows']} 行 / 复核 {summary['reviews']} 条"
              f"（一致 {summary['agreements']}，不一致 {summary['disagreements']}）")
        for warning in result["warnings"]:
            print(f"  提醒：{warning}")
        for problem in result["problems"]:
            print(f"  问题：{problem}")
        print("结论：资料齐全，可通过" if not result["problems"] else "结论：资料不完整，不可作为验收证据")

    return 0 if not result["problems"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""校验一次现场验收交付包是否齐全、可核对。

验收包是一组机器可检查的文件：拍摄清单、圈舍台账、双人复核记录、报告。
这里只判断"资料是否齐全且自洽"，不判断模型精度，也不代替现场人员。
"""

from __future__ import annotations

import csv
from hashlib import sha256
from pathlib import Path

REQUIRED_FILES = {
    "shooting-list.csv": ["clip_id", "pen_id", "camera_id", "started_at", "duration_seconds",
                          "resolution", "file_path", "sha256", "operator", "coverage_note"],
    "pen-ledger.csv": ["pen_id", "recorded_at", "expected_count", "count_a", "count_b",
                       "operator_a", "operator_b", "gate_log_checked", "notes"],
    "double-review.csv": ["clip_id", "pen_id", "check_type", "time_seconds",
                          "verdict_a", "verdict_b", "note"],
}
REPORT_FILE = "report.md"
MIN_CLIP_SECONDS = 60


def _read_rows(path: Path) -> tuple[list[str], list[dict]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [row for row in reader]


def _as_int(value: str):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def check_field_acceptance(root: str | Path) -> dict:
    root = Path(root)
    problems: list[str] = []
    warnings: list[str] = []

    for name, columns in REQUIRED_FILES.items():
        path = root / name
        if not path.is_file():
            problems.append(f"缺少必需文件：{name}")
            continue
        header, _ = _read_rows(path)
        missing = [column for column in columns if column not in header]
        if missing:
            problems.append(f"{name} 缺少列：{', '.join(missing)}")

    report = root / REPORT_FILE
    if not report.is_file():
        problems.append(f"缺少必需文件：{REPORT_FILE}")
    else:
        text = report.read_text(encoding="utf-8")
        for placeholder in ("TODO", "TBD", "待填写"):
            if placeholder in text:
                problems.append(f"{REPORT_FILE} 仍有未填写的占位符：{placeholder}")

    clips = 0
    shooting = root / "shooting-list.csv"
    if shooting.is_file():
        _, rows = _read_rows(shooting)
        clips = len(rows)
        for index, row in enumerate(rows, start=2):
            clip = (row.get("file_path") or "").strip()
            if not clip:
                problems.append(f"shooting-list.csv 第 {index} 行没有 file_path")
                continue
            video = root / clip
            if not video.is_file():
                problems.append(f"shooting-list.csv 第 {index} 行视频不存在：{clip}")
                continue
            expected = (row.get("sha256") or "").strip().lower()
            actual = sha256(video.read_bytes()).hexdigest()
            if expected != actual:
                problems.append(f"{clip} 的 sha256 与拍摄清单不符")
            seconds = _as_int(row.get("duration_seconds", ""))
            if seconds is None:
                problems.append(f"shooting-list.csv 第 {index} 行 duration_seconds 不是整数")
            elif seconds < MIN_CLIP_SECONDS:
                warnings.append(f"{clip} 只有 {seconds} 秒，短于协议要求的一次连续录制")

    ledger_rows = 0
    ledger = root / "pen-ledger.csv"
    if ledger.is_file():
        _, rows = _read_rows(ledger)
        ledger_rows = len(rows)
        for index, row in enumerate(rows, start=2):
            for field in ("expected_count", "count_a", "count_b"):
                if _as_int(row.get(field, "")) is None:
                    problems.append(f"pen-ledger.csv 第 {index} 行 {field} 不是整数")
            if (row.get("gate_log_checked") or "").strip().lower() not in {"yes", "true", "1"}:
                warnings.append(f"pen-ledger.csv 第 {index} 行没有确认已核对出入栏记录")

    agreements = 0
    disagreements = 0
    reviews = 0
    double = root / "double-review.csv"
    if double.is_file():
        _, rows = _read_rows(double)
        reviews = len(rows)
        for index, row in enumerate(rows, start=2):
            first = (row.get("verdict_a") or "").strip()
            second = (row.get("verdict_b") or "").strip()
            if not first or not second:
                problems.append(f"double-review.csv 第 {index} 行缺少一位复核人的结论")
                continue
            if first == second:
                agreements += 1
            else:
                disagreements += 1

    return {
        "root": str(root),
        "problems": problems,
        "warnings": warnings,
        "summary": {
            "clips": clips,
            "ledger_rows": ledger_rows,
            "reviews": reviews,
            "agreements": agreements,
            "disagreements": disagreements,
        },
    }

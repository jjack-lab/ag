import csv
from hashlib import sha256
from pathlib import Path

from cattle_health_app.field_acceptance import check_field_acceptance

CLIP_HEADER = ["clip_id", "pen_id", "camera_id", "started_at", "duration_seconds",
               "resolution", "file_path", "sha256", "operator", "coverage_note"]
LEDGER_HEADER = ["pen_id", "recorded_at", "expected_count", "count_a", "count_b",
                 "operator_a", "operator_b", "gate_log_checked", "notes"]
REVIEW_HEADER = ["clip_id", "pen_id", "check_type", "time_seconds",
                 "verdict_a", "verdict_b", "note"]


def _write_csv(path: Path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def build_pack(root: Path) -> Path:
    video = root / "videos" / "clip-01.mp4"
    video.parent.mkdir(parents=True, exist_ok=True)
    video.write_bytes(b"fake-video-bytes")
    digest = sha256(b"fake-video-bytes").hexdigest()
    _write_csv(root / "shooting-list.csv", CLIP_HEADER, [[
        "clip-01", "PEN-01", "CAM-01", "2026-10-27T08:30:00+08:00", "600",
        "1920x1080", "videos/clip-01.mp4", digest, "张三",
        "固定机位，覆盖完整圈舍，无遮挡",
    ]])
    _write_csv(root / "pen-ledger.csv", LEDGER_HEADER, [[
        "PEN-01", "2026-10-27T08:00:00+08:00", "12", "12", "12",
        "张三", "李四", "yes", "",
    ]])
    _write_csv(root / "double-review.csv", REVIEW_HEADER, [[
        "clip-01", "PEN-01", "pen_count", "0", "match", "match", "",
    ]])
    (root / "report.md").write_text(
        "# 现场验收报告\n\n结论：本轮双人复核一致。\n", encoding="utf-8")
    return root


def test_complete_pack_passes(tmp_path):
    result = check_field_acceptance(build_pack(tmp_path))
    assert result["problems"] == []
    assert result["summary"]["clips"] == 1
    assert result["summary"]["agreements"] == 1


def test_missing_required_file_is_reported(tmp_path):
    pack = build_pack(tmp_path)
    (pack / "double-review.csv").unlink()
    result = check_field_acceptance(pack)
    assert any("double-review.csv" in problem for problem in result["problems"])


def test_video_hash_mismatch_is_reported(tmp_path):
    pack = build_pack(tmp_path)
    (pack / "videos" / "clip-01.mp4").write_bytes(b"tampered")
    result = check_field_acceptance(pack)
    assert any("sha256" in problem for problem in result["problems"])


def test_csv_header_must_match_the_protocol(tmp_path):
    pack = build_pack(tmp_path)
    _write_csv(pack / "pen-ledger.csv", ["pen_id", "count"], [["PEN-01", "12"]])
    result = check_field_acceptance(pack)
    assert any("pen-ledger.csv" in problem for problem in result["problems"])


def test_disagreement_between_two_operators_is_counted_not_failed(tmp_path):
    pack = build_pack(tmp_path)
    _write_csv(pack / "double-review.csv", REVIEW_HEADER, [[
        "clip-01", "PEN-01", "pen_count", "0", "match", "mismatch", "B 认为少 1 头",
    ]])
    result = check_field_acceptance(pack)
    assert result["problems"] == []
    assert result["summary"]["disagreements"] == 1


def test_unfinished_report_placeholder_is_reported(tmp_path):
    pack = build_pack(tmp_path)
    (pack / "report.md").write_text("# 现场验收报告\n\nTODO: 填写结论\n", encoding="utf-8")
    result = check_field_acceptance(pack)
    assert any("TODO" in problem for problem in result["problems"])


def test_cli_exit_code_reflects_completeness(tmp_path, capsys):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from check_field_acceptance import main

    pack = build_pack(tmp_path)
    assert main(["--root", str(pack)]) == 0
    (pack / "pen-ledger.csv").unlink()
    assert main(["--root", str(pack)]) == 1
    assert "资料不完整" in capsys.readouterr().out

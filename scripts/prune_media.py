"""媒体目录清理脚本。

默认只报告、不删除：

    python scripts/prune_media.py

确认后加 ``--apply`` 才真正删除：

    python scripts/prune_media.py --apply

只清理 ``data/media/{uploads,results}`` 下、没有被任何视频任务引用、且超过
保留期（默认 14 天）的文件。数据库本身不动。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from cattle_health_app.media_retention import collect_orphans, prune  # noqa: E402
from cattle_health_app.repository import SQLiteRepository  # noqa: E402


def humanize(size: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="清理未被任务引用的媒体文件")
    parser.add_argument(
        "--root",
        default=str(PROJECT_ROOT / "data" / "media"),
        help="媒体根目录，默认 data/media",
    )
    parser.add_argument(
        "--db",
        default=str(PROJECT_ROOT / "data" / "agrinebula.db"),
        help="SQLite 数据库路径，用于读取任务引用",
    )
    parser.add_argument(
        "--older-than-days",
        type=int,
        default=14,
        help="只清理超过该天数的文件，默认 14",
    )
    parser.add_argument("--apply", action="store_true", help="真正删除；默认仅报告")
    parser.add_argument(
        "--include-uploads",
        action="store_true",
        help="同时清理 uploads 下无引用且超期的文件（默认不动，避免删掉用户原片）",
    )
    args = parser.parse_args(argv)

    media_root = Path(args.root)
    if not media_root.is_dir():
        print(f"[skip] 媒体目录不存在: {media_root}")
        return 0

    jobs = []
    database = Path(args.db)
    if database.is_file():
        repository = SQLiteRepository(database)
        jobs = repository.list_all_video_jobs()
        print(f"[db] 读取任务 {len(jobs)} 条: {database}")
    else:
        print(f"[db] 数据库不存在，按无引用处理: {database}")

    plan = collect_orphans(
        media_root,
        jobs,
        older_than_days=args.older_than_days,
        include_uploads=args.include_uploads,
    )
    print(
        f"[plan] 可清理 {plan['count']} 个文件，"
        f"约 {humanize(plan['total_bytes'])}（超过 {args.older_than_days} 天且无引用）"
    )
    for path in plan["files"]:
        print(f"  - {path}")
    if not plan["files"]:
        return 0
    if not args.apply:
        print("[dry-run] 未删除任何文件；确认后加 --apply")
        return 0

    result = prune(plan["files"])
    print(
        f"[apply] 已删除 {result['deleted']} 个文件，释放 {humanize(result['bytes'])}"
    )
    if result["failed"]:
        print(f"[warn] {len(result['failed'])} 个文件删除失败:")
        for path in result["failed"]:
            print(f"  - {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""媒体目录保留策略：识别并清理不再被任何视频任务引用的结果目录。

默认只处理 ``data/media/results/<job_id>/`` 这类任务专属目录：
- 任务 ID 仍在数据库里的目录一律保留；
- ``.gitkeep``、结果根目录下的零散文件（图片检测输出）默认不动；
- 上传目录默认不动（可能有用户原片），需显式 ``--include-uploads``。

只删除超过保留期（默认 14 天）且没有任何任务引用的文件。
"""

from __future__ import annotations

import time
from pathlib import Path

DEFAULT_OLDER_THAN_DAYS = 14
KEEP_NAMES = {".gitkeep"}


def _string_values(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _string_values(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _string_values(item)


def referenced_files(media_root, jobs):
    """返回任务引用到的文件绝对路径集合（含 source_path 与结果文件）。"""
    root = Path(media_root).resolve()
    references = set()
    for job in jobs:
        if getattr(job, "source_path", None):
            references.add(Path(job.source_path).resolve())
        for value in _string_values(getattr(job, "result", None)):
            text = value.strip()
            if not text:
                continue
            candidate = Path(text)
            if candidate.is_absolute():
                references.add(candidate.resolve())
            else:
                references.add((root / candidate).resolve())
                references.add((root / "results" / candidate).resolve())
    return references


def _file_stats(files):
    total = 0
    newest = 0.0
    for path in files:
        try:
            stat = path.stat()
        except OSError:
            continue
        total += stat.st_size
        newest = max(newest, stat.st_mtime)
    return total, newest


def collect_orphans(
    media_root,
    jobs,
    *,
    older_than_days: int = DEFAULT_OLDER_THAN_DAYS,
    include_uploads: bool = False,
    now: float | None = None,
):
    """列出可清理文件，返回 {"files": [...], "total_bytes": n, "count": n}。"""
    root = Path(media_root).resolve()
    references = referenced_files(root, jobs)
    job_ids = {
        getattr(job, "id", None) for job in jobs if getattr(job, "id", None)
    }
    current = time.time() if now is None else now
    cutoff = current - older_than_days * 86400

    files = []
    total_bytes = 0

    def add_files(candidates):
        nonlocal total_bytes
        for path in candidates:
            resolved = path.resolve()
            if resolved in references:
                continue
            try:
                if path.stat().st_mtime > cutoff:
                    continue
            except OSError:
                continue
            files.append(resolved)
            try:
                total_bytes += path.stat().st_size
            except OSError:
                pass

    results_root = root / "results"
    if results_root.is_dir():
        for entry in sorted(results_root.iterdir()):
            if not entry.is_dir() or entry.name in job_ids:
                continue
            candidates = [
                path
                for path in entry.rglob("*")
                if path.is_file() and path.name not in KEEP_NAMES
            ]
            if candidates:
                add_files(candidates)

    if include_uploads:
        uploads_root = root / "uploads"
        if uploads_root.is_dir():
            add_files(
                path
                for path in uploads_root.rglob("*")
                if path.is_file() and path.name not in KEEP_NAMES
            )

    files.sort()
    return {"files": files, "total_bytes": total_bytes, "count": len(files)}


def prune(files):
    """删除给定文件，返回 {"deleted": n, "bytes": n, "failed": [路径]}。"""
    deleted = 0
    freed = 0
    failed = []
    touched_dirs = set()
    for path in files:
        path = Path(path)
        try:
            size = path.stat().st_size
            path.unlink()
        except FileNotFoundError:
            continue
        except OSError:
            failed.append(str(path))
            continue
        deleted += 1
        freed += size
        touched_dirs.add(path.parent)

    # 清掉因此变空的结果子目录（保留 results 根与 .gitkeep）。
    for directory in sorted(touched_dirs, key=lambda item: len(str(item)), reverse=True):
        try:
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
        except OSError:
            pass

    return {"deleted": deleted, "bytes": freed, "failed": failed}

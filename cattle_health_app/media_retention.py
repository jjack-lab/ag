"""媒体目录保留策略：识别并清理不再被任何视频任务引用的文件。

只清理 ``data/media/uploads`` 与 ``data/media/results`` 下、既没有数据库引用、
又超过保留期的普通文件；不碰 evaluations、模型和项目其它目录。
"""

from __future__ import annotations

import time
from pathlib import Path

MEDIA_SECTIONS = ("uploads", "results")
DEFAULT_OLDER_THAN_DAYS = 14


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


def collect_orphans(
    media_root,
    jobs,
    *,
    older_than_days: int = DEFAULT_OLDER_THAN_DAYS,
    now: float | None = None,
):
    """列出可清理文件，返回 {"files": [...], "total_bytes": n, "count": n}。"""
    root = Path(media_root).resolve()
    references = referenced_files(root, jobs)
    current = time.time() if now is None else now
    cutoff = current - older_than_days * 86400
    files = []
    total_bytes = 0
    for section in MEDIA_SECTIONS:
        section_root = root / section
        if not section_root.is_dir():
            continue
        for path in section_root.rglob("*"):
            if not path.is_file():
                continue
            resolved = path.resolve()
            if resolved in references:
                continue
            try:
                modified = path.stat().st_mtime
            except OSError:
                continue
            if modified > cutoff:
                continue
            files.append(resolved)
            try:
                total_bytes += path.stat().st_size
            except OSError:
                pass
    files.sort()
    return {"files": files, "total_bytes": total_bytes, "count": len(files)}


def prune(files):
    """删除给定文件，返回 {"deleted": n, "bytes": n, "failed": [路径]}。"""
    deleted = 0
    freed = 0
    failed = []
    for path in files:
        try:
            size = Path(path).stat().st_size
            Path(path).unlink()
        except FileNotFoundError:
            continue
        except OSError:
            failed.append(str(path))
            continue
        deleted += 1
        freed += size
    return {"deleted": deleted, "bytes": freed, "failed": failed}

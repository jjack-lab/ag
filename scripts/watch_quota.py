#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Codex 额度监听器。

盯住 ~/.codex/sessions/ 下本地会话日志（JSONL）中新增的额度/限流报错。
一旦检测到：
  1) 对主仓库及所有 git worktree 自动做 WIP 提交（无改动则跳过）；
  2) 在仓库根 HANDOFF.md 的「中断记录」小节追加一条现场记录（含来源会话路径）；
  3) 弹窗 + 蜂鸣，提醒用户切换到 ZCode。

设计要点：
- 只识别启动之后新写入的日志内容，启动前已有的报错不追溯（应于开工前启动）；
- 只把带 error 类型标记的日志行当作候选，避免普通聊天文本里提到"额度"造成误报；
- 仅用标准库；不动任何远端，不自动启动其他 AI。
"""

import argparse
import ctypes
import datetime as dt
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

# 报错特征词（小写匹配；中文不受 lower 影响）。新增特征词在这里补充。
MARKERS = (
    "usage_limit_reached",
    "usage limit reached",
    "hit your usage limit",
    "you've hit",
    "you have hit your usage",
    "rate limit exceeded",
    "rate_limit_exceeded",
    "status 429",
    "429 too many requests",
    "too many requests",
    "quota exceeded",
    "quota reached",
    "使用额度",
    "额度已用",
    "已达到使用限制",
)

# 日志行里 type 字段命中这些值才算错误事件
ERROR_TYPES = {"error", "stream_error", "turn_aborted", "error_details"}

HANDOFF_HEADER = "## 中断记录"


def log(msg):
    stamp = dt.datetime.now().strftime("%H:%M:%S")
    print("[%s] %s" % (stamp, msg), flush=True)


def is_error_line(line):
    """只把带 error 类型标记的 JSON 行当作候选，普通对话/工具输出不算。"""
    try:
        obj = json.loads(line)
    except Exception:
        return '"error"' in line
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            t = cur.get("type")
            if isinstance(t, str) and t in ERROR_TYPES:
                return True
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return False


def match_marker(line):
    low = line.lower()
    for m in MARKERS:
        if m in low:
            return m
    return None


def run_git(repo, *args):
    return subprocess.run(
        ["git", "-c", "core.quotepath=false", "-C", str(repo)] + list(args),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def wip_commit_all(repo_root):
    """对主仓库和所有 worktree 做 WIP 提交，返回 '目录@短哈希' 描述列表。"""
    results = []
    proc = run_git(repo_root, "worktree", "list", "--porcelain")
    roots = []
    if proc.returncode == 0:
        for ln in proc.stdout.splitlines():
            if ln.startswith("worktree "):
                roots.append(Path(ln[len("worktree "):].strip().strip('"')))
    if not roots:
        roots = [repo_root]

    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    for root in roots:
        if not root.exists():
            continue
        status = run_git(root, "status", "--porcelain")
        if status.returncode != 0 or not status.stdout.strip():
            continue
        run_git(root, "add", "-A")
        staged = run_git(root, "diff", "--cached", "--quiet")
        if staged.returncode == 0:
            continue  # 没有可提交内容
        commit = run_git(root, "commit", "-m", "wip: 额度监听自动保存 @ " + ts)
        head = run_git(root, "rev-parse", "--short", "HEAD")
        short = head.stdout.strip() if head.returncode == 0 else "?"
        results.append("%s@%s" % (root, short))
        if commit.returncode == 0:
            log("WIP 提交完成：%s -> %s" % (root, short))
        else:
            log("WIP 提交失败：%s（%s）" % (root, commit.stderr.strip()[:120]))
    return results


def append_handoff(repo_root, entry):
    """把中断记录插入 HANDOFF.md 的「中断记录」小节顶部；无该小节则追加在末尾。"""
    path = repo_root / "HANDOFF.md"
    try:
        content = path.read_text(encoding="utf-8") if path.exists() else ""
    except OSError:
        content = ""
    lines = content.splitlines(keepends=True)
    for i, ln in enumerate(lines):
        if ln.strip() == HANDOFF_HEADER:
            lines.insert(i + 1, entry + "\n")
            path.write_text("".join(lines), encoding="utf-8")
            return
    if content and not content.endswith("\n"):
        content += "\n"
    content += "\n%s\n%s\n" % (HANDOFF_HEADER, entry)
    path.write_text(content, encoding="utf-8")


def popup(title, message):
    def _show():
        try:
            import winsound
            winsound.MessageBeep(0x30)
        except Exception:
            pass
        try:
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x40)
        except Exception:
            pass

    threading.Thread(target=_show, daemon=True).start()


def on_trigger(repo_root, session_file, marker, line, no_commit, no_popup):
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log("检测到额度/限流报错！匹配词：%s" % marker)
    log("来源会话：%s" % session_file)
    commits = [] if no_commit else wip_commit_all(repo_root)
    commit_txt = "；".join(commits) if commits else "（无需提交或 --no-commit 跳过）"
    snippet = line[:200].replace("\n", " ")
    entry = (
        "- **%s** 监听脚本检测到额度报错（匹配 `%s`）。来源会话：`%s`。"
        "自动 WIP 提交：%s。接手方请读取该会话文件末尾还原上下文，并从「下一步」清单继续。"
        "原始报错片段：`%s`" % (ts, marker, session_file, commit_txt, snippet)
    )
    try:
        append_handoff(repo_root, entry)
        log("已在 HANDOFF.md 追加中断记录")
    except Exception as exc:
        log("HANDOFF.md 写入失败：%s" % exc)
    if not no_popup:
        popup(
            "Codex 额度用尽 — 现场已自动保存",
            "检测到 Codex 额度/限流报错。\n\n"
            "已完成：WIP 提交（%s）\n"
            "已在 HANDOFF.md 记录中断点。\n\n"
            "请切换到 ZCode，对它说“继续”即可接手。" % commit_txt,
        )


def watch(sessions_root, repo_root, interval, no_commit, no_popup):
    offsets = {}   # 文件 -> 已读到的字节偏移
    tails = {}     # 文件 -> 末尾不完整行的残余文本
    alerted = set()

    for f in sessions_root.rglob("*.jsonl"):
        try:
            offsets[f] = f.stat().st_size
        except OSError:
            pass
    log("开始监听：会话目录 %s" % sessions_root)
    log("仓库根目录：%s（主仓库与所有 worktree 都会被自动 WIP 提交）" % repo_root)
    log("基线文件数：%d。只识别启动后新增的报错；Ctrl+C 退出。" % len(offsets))

    while True:
        time.sleep(interval)
        try:
            files = list(sessions_root.rglob("*.jsonl"))
        except OSError:
            continue
        for f in files:
            try:
                size = f.stat().st_size
            except OSError:
                continue
            if f not in offsets:
                # 首次见到的新文件：记基线跳过历史内容，之后的新增才参与检测
                offsets[f] = size
                tails[f] = ""
                continue
            start = offsets[f]
            if size < start:  # 文件被截断重写，从头读
                start = 0
                tails[f] = ""
            if size == start:
                continue
            try:
                with f.open("rb") as fh:
                    fh.seek(start)
                    raw = fh.read()
            except OSError:
                continue
            offsets[f] = size
            text = tails.get(f, "") + raw.decode("utf-8", errors="replace")
            parts = text.split("\n")
            tails[f] = parts.pop()
            for line in parts:
                line = line.strip()
                if not line or f in alerted:
                    continue
                if is_error_line(line):
                    marker = match_marker(line)
                    if marker:
                        alerted.add(f)
                        on_trigger(repo_root, f, marker, line, no_commit, no_popup)
                        break


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Codex 额度监听器")
    ap.add_argument("--repo", default=str(Path(__file__).resolve().parent.parent),
                    help="仓库根目录（默认：脚本所在仓库）")
    ap.add_argument("--sessions-dir", default=str(Path.home() / ".codex" / "sessions"),
                    help="Codex 本地会话日志目录")
    ap.add_argument("--interval", type=int, default=20, help="轮询间隔秒数（默认 20）")
    ap.add_argument("--no-commit", action="store_true", help="只报警，不做 WIP 提交")
    ap.add_argument("--no-popup", action="store_true", help="不弹窗（调试用）")
    args = ap.parse_args()

    repo = Path(args.repo)
    sessions = Path(args.sessions_dir)
    if not sessions.exists():
        log("会话目录不存在：%s" % sessions)
        sys.exit(1)
    if not (repo / ".git").exists():
        log("不是 git 仓库：%s" % repo)
        sys.exit(1)
    watch(sessions, repo, args.interval, args.no_commit, args.no_popup)


if __name__ == "__main__":
    main()

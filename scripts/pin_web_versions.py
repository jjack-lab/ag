"""把 web/package.json 的依赖版本锁定到 package-lock.json 已解析的版本。

用法：

    python scripts/pin_web_versions.py --check   # 只检查，不一致返回 1
    python scripts/pin_web_versions.py           # 写入精确版本

只改 ``web/package.json`` 与 ``web/package-lock.json`` 的根依赖声明，不改已安装树。
之后 `npm ci` 会严格按锁文件安装。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = PROJECT_ROOT / "web"
PACKAGE_JSON = WEB_ROOT / "package.json"
PACKAGE_LOCK = WEB_ROOT / "package-lock.json"
SECTIONS = ("dependencies", "devDependencies")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, data: dict) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def locked_version(lock: dict, name: str) -> str | None:
    entry = lock.get("packages", {}).get(f"node_modules/{name}")
    return entry.get("version") if entry else None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="锁定前端依赖版本")
    parser.add_argument("--check", action="store_true", help="只检查不写入")
    args = parser.parse_args(argv)

    lock = load(PACKAGE_LOCK)
    package = load(PACKAGE_JSON)
    root = lock.setdefault("packages", {}).setdefault("", {})

    mismatches = []
    for section in SECTIONS:
        declared = package.get(section, {})
        for name in list(declared):
            installed = locked_version(lock, name)
            if installed is None:
                mismatches.append((section, name, declared[name], "未锁定"))
                continue
            if declared[name] != installed:
                mismatches.append((section, name, declared[name], installed))

    if args.check:
        if mismatches:
            print(f"[check] {len(mismatches)} 个依赖版本不一致：")
            for section, name, declared, installed in mismatches:
                print(f"  - {section}.{name}: {declared} -> {installed}")
            return 1
        print("[check] 全部依赖已锁定到锁文件版本")
        return 0

    changes = 0
    for section, name, declared, installed in mismatches:
        if installed == "未锁定":
            print(f"[warn] 跳过 {name}: 锁文件里没有 node_modules 条目")
            continue
        package[section][name] = installed
        root.setdefault(section, {})[name] = installed
        print(f"[pin] {name}: {declared} -> {installed}")
        changes += 1

    if changes:
        dump(PACKAGE_JSON, package)
        dump(PACKAGE_LOCK, lock)
        print(f"[done] 已更新 {changes} 个依赖声明")
    else:
        print("[done] 无需修改")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

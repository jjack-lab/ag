"""本地服务运行参数，默认只监听回环地址。

局域网演示需要显式设置 ``AGRINEBULA_HOST=0.0.0.0``，并且应同时确认网络环境。
目前没有鉴权层，因此默认值刻意保守。
"""

from __future__ import annotations

import os

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def server_host() -> str:
    value = os.environ.get("AGRINEBULA_HOST", "").strip()
    return value or DEFAULT_HOST


def server_port() -> int:
    value = os.environ.get("AGRINEBULA_PORT", "").strip()
    if not value:
        return DEFAULT_PORT
    try:
        port = int(value)
    except ValueError as error:
        raise ValueError(f"AGRINEBULA_PORT 不是整数: {value!r}") from error
    if not 1 <= port <= 65535:
        raise ValueError(f"AGRINEBULA_PORT 超出范围: {port}")
    return port

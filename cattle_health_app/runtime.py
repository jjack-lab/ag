"""本地服务运行参数，默认只监听回环地址。

局域网演示需要显式设置 ``AGRINEBULA_HOST=0.0.0.0``，并且应同时确认网络环境。
监听非回环地址时必须设置 ``AGRINEBULA_API_TOKEN``，否则服务拒绝启动：
上传原片、结果视频与人工记录都不应该在没有令牌的情况下对局域网开放。
"""

from __future__ import annotations

import os

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]"}


def api_token_from_env() -> str | None:
    value = os.environ.get("AGRINEBULA_API_TOKEN", "").strip()
    return value or None


def ensure_bind_is_safe(host: str, token: str | None) -> None:
    """监听非回环地址时必须带访问令牌，否则拒绝启动。"""
    if token:
        return
    if host.strip().lower() in LOOPBACK_HOSTS:
        return
    raise ValueError(
        f"监听 {host} 会把上传、结果视频和人工记录暴露到局域网，"
        "但没有设置 AGRINEBULA_API_TOKEN：请先设置访问令牌，或只监听 127.0.0.1。"
    )


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

"""search-toolkit 公共定义。

零依赖：仅使用 Python 3.13 stdlib。所有 backend / 站点适配器 / 工具脚本
必须通过本模块的统一定义实现错误处理与结果归一化。
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any


class BackendError(Exception):
    """Backend 调用失败的统一异常。

    `retryable` 指网络层瞬时错误（429 / 5xx / 超时），调用方可考虑重试；
    其余 4xx 与解析错误视为永久失败。
    """

    def __init__(self, backend: str, message: str, *, retryable: bool = False, http_status: int | None = None):
        super().__init__(f"[{backend}] {message}")
        self.backend = backend
        self.message = message
        self.retryable = retryable
        self.http_status = http_status  # HTTP 错误码（如 401/403），非 HTTP 错误为 None


def env(name: str) -> str | None:
    """读取环境变量，空字符串视为未设置。"""
    val = os.environ.get(name, "").strip()
    return val or None


def emit(payload: dict[str, Any]) -> None:
    """统一 JSON 输出到 stdout，便于 subagent / 上层脚本解析。"""
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def normalize_result(
    title: str,
    url: str,
    snippet: str = "",
    **extra: Any,
) -> dict[str, Any]:
    """统一搜索结果结构。所有 backend 与适配器必须返回此结构。"""
    return {
        "title": (title or "").strip(),
        "url": (url or "").strip(),
        "snippet": (snippet or "").strip(),
        "extra": extra,
    }

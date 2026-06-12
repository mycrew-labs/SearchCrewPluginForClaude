"""统一 HTTP 客户端（stdlib urllib，零依赖）。

所有 backend / 站点适配器调用 HTTP 必须经此模块，便于：
- 统一超时、错误分类
- 在出口统一调用 usage.record()（cost 打点）
- 集中拦截 retryable / non-retryable 错误
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from . import BackendError

DEFAULT_TIMEOUT = 30
USER_AGENT = "search-crew/0.1 (+https://github.com/mycrew-labs/search-crew)"

# 站点调用上限（同 run 同 backend 计数器）
# - run_id 口径与 runtime.run_id() 一致：SEARCH_CREW_RUN_ID > CLAUDE_CODE_SESSION_ID > 兜底
# - dict 跨进程不共享；每个 subagent 是独立 Python 进程，各自计数（设计明确接受）
# - 默认：AI backend 1 次、非 AI backend 2 次；可在 ~/.config/search-crew/limits.yaml 覆盖
_call_counter: dict[tuple[str, str], int] = {}
_AI_BACKENDS = frozenset({"grok", "gemini", "doubao"})
_DEFAULT_AI_CAP = 1
_DEFAULT_NON_AI_CAP = 2


def _run_id() -> str:
    """run_id：复用 runtime.run_id()（统一口径），异常兜底 PID。"""
    try:
        from . import runtime  # noqa: PLC0415  延迟导入

        return runtime.run_id()
    except Exception:
        return f"pid-{os.getpid()}"


def _cap_for(backend: str) -> int:
    """读 limits.yaml call_cap 段，缺失回落默认。"""
    try:
        from . import config  # noqa: PLC0415  延迟导入

        limits = config.load_limits() or {}
        cap_cfg = limits.get("call_cap") or {}
        if backend in _AI_BACKENDS:
            return int(cap_cfg.get("ai_backend", _DEFAULT_AI_CAP))
        return int(cap_cfg.get("non_ai_backend", _DEFAULT_NON_AI_CAP))
    except Exception:
        return _DEFAULT_AI_CAP if backend in _AI_BACKENDS else _DEFAULT_NON_AI_CAP


def _check_and_increment_cap(backend: str, query: str | None = None, cap_exempt: bool = False) -> None:
    """达到上限直接 raise；未达上限自增。

    `cap_exempt=True`：读取 / 抓取类操作（jina-reader、fetch.py 直连探测）豁免上限——
    上限只约束搜索源，读取已知 URL 是正常多次操作（evidence-search 抓 top N、deep-search 多页深挖）。
    """
    if cap_exempt:
        return
    key = (_run_id(), backend)
    current = _call_counter.get(key, 0)
    cap = _cap_for(backend)
    if current >= cap:
        # 上限触发也要打点（status: call_cap_exceeded），保留痕迹供 usage-summary 渲染「已跳过」
        try:
            from . import usage  # noqa: PLC0415  延迟导入

            usage.record(
                backend=backend,
                endpoint="call_cap_exceeded",
                status="call_cap_exceeded",
                latency_ms=0,
                tokens_or_units=0,
                query=query,
            )
        except Exception:
            pass
        raise BackendError(
            backend,
            f"触发站点调用上限（cap={cap}，已用 {current}）",
            retryable=False,
        )
    _call_counter[key] = current + 1


def reset_call_counter() -> None:
    """供测试 / 多 run 场景显式清空计数器（生产代码不应调用）。"""
    _call_counter.clear()


def _record_call(
    *,
    backend: str,
    endpoint: str,
    status: int | str,
    latency_ms: int,
    units: int | None,
    query: str | None = None,
) -> None:
    """打点钩子。延迟 import 避免循环依赖。失败不阻塞业务。"""
    try:
        from . import usage  # noqa: PLC0415  延迟导入

        usage.record(
            backend=backend,
            endpoint=endpoint,
            status=status,
            latency_ms=latency_ms,
            tokens_or_units=units,
            query=query,
        )
    except Exception as e:  # 打点不应阻塞业务
        import sys

        print(f"[_http] usage.record failed: {e}", file=sys.stderr)


def request_json(
    method: str,
    url: str,
    *,
    backend: str,
    endpoint: str,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    json_body: Any = None,
    timeout: int = DEFAULT_TIMEOUT,
    units: int | None = 1,
    query: str | None = None,
    cap_exempt: bool = False,
) -> Any:
    """发起 JSON 请求并返回反序列化结果。

    `backend` / `endpoint` 用于打点；`units` 用于 cost 估算（默认 1 次请求 = 1 unit）；
    `query` 可选，搜索类 backend 建议传，用于「搜索摘要」段渲染；
    `cap_exempt` 读取/抓取类操作豁免站点调用上限（见 `_check_and_increment_cap`）。
    """
    _check_and_increment_cap(backend, query=query, cap_exempt=cap_exempt)

    if params:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{urllib.parse.urlencode(params, doseq=True)}"

    data = None
    final_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        final_headers["Content-Type"] = "application/json"
    if headers:
        final_headers.update(headers)

    req = urllib.request.Request(url, data=data, method=method, headers=final_headers)
    start = time.monotonic()
    status: int | str = "error"
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        status = e.code
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:400]
        except Exception:
            pass
        retryable = e.code in (429, 502, 503, 504)
        raise BackendError(backend, f"HTTP {e.code}: {body or e.reason}", retryable=retryable, http_status=e.code) from e
    except urllib.error.URLError as e:
        status = "network-error"
        raise BackendError(backend, f"网络错误: {e.reason}", retryable=True) from e
    except TimeoutError as e:
        status = "timeout"
        raise BackendError(backend, "请求超时", retryable=True) from e
    finally:
        _record_call(
            backend=backend,
            endpoint=endpoint,
            status=status,
            latency_ms=int((time.monotonic() - start) * 1000),
            units=units,
            query=query,
        )

    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise BackendError(backend, f"非 JSON 响应: {raw[:200]}") from e


def request_text(
    method: str,
    url: str,
    *,
    backend: str,
    endpoint: str,
    headers: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    units: int | None = 1,
    query: str | None = None,
    cap_exempt: bool = False,
) -> str:
    """发起请求返回原文（用于抓取页面 / markdown）。"""
    return _request_text_impl(
        method, url, backend=backend, endpoint=endpoint, headers=headers,
        timeout=timeout, units=units, query=query, cap_exempt=cap_exempt,
    )[0]


def request_text_meta(
    method: str,
    url: str,
    *,
    backend: str,
    endpoint: str,
    headers: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    units: int | None = 1,
    query: str | None = None,
    cap_exempt: bool = False,
) -> tuple[str, str]:
    """同 request_text，但额外返回响应 Content-Type（小写、去参数），供 fetch.py 判 raw/HTML。"""
    return _request_text_impl(
        method, url, backend=backend, endpoint=endpoint, headers=headers,
        timeout=timeout, units=units, query=query, cap_exempt=cap_exempt,
    )


def request_status_text(
    method: str,
    url: str,
    *,
    backend: str,
    endpoint: str,
    headers: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    units: int | None = 1,
    query: str | None = None,
    cap_exempt: bool = False,
) -> tuple[int, str]:
    """发起请求返回 (status, text)，HTTP 非 2xx 不抛异常（供轮询类状态机分支）。

    仅网络错误 / 超时仍 raise BackendError。打点与 cap 语义同其余 helper。
    """
    _check_and_increment_cap(backend, query=query, cap_exempt=cap_exempt)

    final_headers = {"User-Agent": USER_AGENT}
    if headers:
        final_headers.update(headers)
    req = urllib.request.Request(url, method=method, headers=final_headers)
    start = time.monotonic()
    status: int | str = "error"
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        status = e.code
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        return e.code, body
    except urllib.error.URLError as e:
        status = "network-error"
        raise BackendError(backend, f"网络错误: {e.reason}", retryable=True) from e
    except TimeoutError as e:
        status = "timeout"
        raise BackendError(backend, "请求超时", retryable=True) from e
    finally:
        _record_call(
            backend=backend,
            endpoint=endpoint,
            status=status,
            latency_ms=int((time.monotonic() - start) * 1000),
            units=units,
            query=query,
        )


def _request_text_impl(
    method: str,
    url: str,
    *,
    backend: str,
    endpoint: str,
    headers: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    units: int | None = 1,
    query: str | None = None,
    cap_exempt: bool = False,
) -> tuple[str, str]:
    """返回 (text, content_type)。content_type 为小写、去掉 `; charset=` 等参数。"""
    _check_and_increment_cap(backend, query=query, cap_exempt=cap_exempt)

    final_headers = {"User-Agent": USER_AGENT}
    if headers:
        final_headers.update(headers)
    req = urllib.request.Request(url, method=method, headers=final_headers)
    start = time.monotonic()
    status: int | str = "error"
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            text = resp.read().decode("utf-8", errors="replace")
            ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            return text, ctype
    except urllib.error.HTTPError as e:
        status = e.code
        raise BackendError(backend, f"HTTP {e.code}: {e.reason}", retryable=e.code in (429, 502, 503, 504), http_status=e.code) from e
    except urllib.error.URLError as e:
        status = "network-error"
        raise BackendError(backend, f"网络错误: {e.reason}", retryable=True) from e
    finally:
        _record_call(
            backend=backend,
            endpoint=endpoint,
            status=status,
            latency_ms=int((time.monotonic() - start) * 1000),
            units=units,
            query=query,
        )

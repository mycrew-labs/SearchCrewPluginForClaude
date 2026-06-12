"""universal-page-fetcher（真实已登录浏览器执行端）客户端。

服务端：https://github.com/mycrew-labs/universal-page-fetcher
（Cloudflare Worker 网关 + 用户真实 Chrome 扩展）。本模块按其调用方契约实现轮询客户端。

连接配置沿用对方自有约定，本插件不重复存储（避免双源漂移）：
  1. 环境变量 UNIVERSAL_PAGE_FETCHER_WORKER_URL / UNIVERSAL_PAGE_FETCHER_PASSWORD
  2. ~/.config/universal-page-fetcher/config.json（字段 workerUrl / password）
两处都没有 = 升级层不可用，调用方静默跳过。

契约要点：
- GET /health：执行端在线检查（extensionOnline 必须为 true）；每进程只探一次，结果缓存
- GET /fetch?url=<encoded>：快任务直接 200 给结果；慢任务 202 {jobId} → ?job= 每 2s 续等
- 已拿到 jobId 后的单次网络错误不判失败（任务仍在服务端跑），连续 10 次才放弃
- 结果只交付一次（交付即清），404 表示 job 过期 → 重发一次完整抓取
- coverage.suspectIncomplete=true 表示可能没抓全 → 按失败处理（要么抓全，要么明确告知）

红线：密码值 MUST NOT 出现在 stdout / stderr / 异常文本中。
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import time
import urllib.parse

from . import BackendError
from . import _http

_BACKEND = "universal-page-fetcher"
_POLL_INTERVAL_SEC = 2
_MAX_CONSECUTIVE_NET_FAILS = 10

# 进程级缓存：连接配置 + health 探测结果。401 等终态错误也会把可用性置 False，
# 避免批量抓取时对同一个错误反复撞墙。
_availability_cache: bool | None = None


def _load_conn() -> tuple[str, str] | None:
    """读连接配置：env 优先，其次 ~/.config/universal-page-fetcher/config.json。"""
    url = (os.environ.get("UNIVERSAL_PAGE_FETCHER_WORKER_URL") or "").strip()
    pwd = os.environ.get("UNIVERSAL_PAGE_FETCHER_PASSWORD") or ""
    if url and pwd:
        return url.rstrip("/"), pwd
    cfg_path = pathlib.Path.home() / ".config" / "universal-page-fetcher" / "config.json"
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        url = (cfg.get("workerUrl") or "").strip()
        pwd = cfg.get("password") or ""
        if url and pwd:
            return url.rstrip("/"), pwd
    except Exception:
        pass
    return None


def _mark_unavailable() -> None:
    global _availability_cache
    _availability_cache = False


def available() -> bool:
    """升级层是否可用：有连接配置 + /health 显示执行端浏览器在线。每进程只探一次。"""
    global _availability_cache
    if _availability_cache is not None:
        return _availability_cache
    conn = _load_conn()
    if conn is None:
        _availability_cache = False
        return False
    worker, pwd = conn
    try:
        data = _http.request_json(
            "GET", f"{worker}/health", backend=_BACKEND, endpoint="health",
            headers={"Authorization": f"Bearer {pwd}"}, timeout=15, cap_exempt=True,
        )
        _availability_cache = bool(isinstance(data, dict) and data.get("extensionOnline"))
        if not _availability_cache:
            print("[real-browser] 执行端浏览器离线，本次升级层跳过", file=sys.stderr)
    except BackendError as e:
        # 不透传异常文本里的 header；401 给固定文案
        if e.http_status == 401:
            print("[real-browser] 鉴权失败（401），请核对 universal-page-fetcher 配置", file=sys.stderr)
        else:
            print(f"[real-browser] health 探测失败（HTTP {e.http_status or '网络错误'}），升级层跳过", file=sys.stderr)
        _availability_cache = False
    return _availability_cache


def _parse_result(body: str) -> dict | None:
    """解析 200 结果；coverage.suspectIncomplete=true 按约定判失败。"""
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        print("[real-browser] 结果非 JSON，判失败", file=sys.stderr)
        return None
    coverage = data.get("coverage") or {}
    if coverage.get("suspectIncomplete"):
        print("[real-browser] coverage.suspectIncomplete=true，可能没抓全，按失败处理", file=sys.stderr)
        return None
    if not (data.get("markdown") or "").strip():
        return None
    return {"title": data.get("title"), "markdown": data["markdown"], "coverage": coverage}


def fetch_page(url: str, wait_sec: int) -> dict | None:
    """经真实浏览器执行端抓取一个 URL。

    成功返回 {"title", "markdown", "coverage"}；任何失败（不可用 / 超时 / 残缺 / 被
    拒）返回 None，由调用方决定回落分支。本函数不抛异常。
    """
    if not available():
        return None
    conn = _load_conn()
    if conn is None:  # available() 为 True 时不会发生，防御一手
        return None
    worker, pwd = conn
    headers = {"Authorization": f"Bearer {pwd}"}
    fresh_target = f"{worker}/fetch?url={urllib.parse.quote(url, safe='')}"

    deadline = time.monotonic() + max(30, wait_sec)
    target = fresh_target
    job_id: str | None = None
    net_fails = 0
    restarted = False       # 404（job 过期）只重发一次完整抓取
    retried_502 = False     # 502（抓取中断）只重试一次

    while time.monotonic() < deadline:
        try:
            status, body = _http.request_status_text(
                "GET", target, backend=_BACKEND, endpoint="fetch",
                headers=headers, timeout=30, cap_exempt=True, query=url,
            )
            net_fails = 0
        except BackendError:
            # 网络抖动：已拿到 jobId 时任务仍在服务端跑，继续带 ?job= 重试
            net_fails += 1
            if job_id is None or net_fails >= _MAX_CONSECUTIVE_NET_FAILS:
                print("[real-browser] 网络连续失败，放弃本次升级抓取", file=sys.stderr)
                return None
            time.sleep(_POLL_INTERVAL_SEC)
            continue

        if status == 200:
            return _parse_result(body)
        if status == 202:
            try:
                job_id = json.loads(body)["jobId"]
            except Exception:
                print("[real-browser] 202 响应缺 jobId，判失败", file=sys.stderr)
                return None
            target = f"{worker}/fetch?job={job_id}"
            time.sleep(_POLL_INTERVAL_SEC)
            continue
        if status == 401:
            print("[real-browser] 鉴权失败（401），请核对 universal-page-fetcher 配置", file=sys.stderr)
            _mark_unavailable()
            return None
        if status == 503:
            print("[real-browser] 执行端浏览器离线（503）", file=sys.stderr)
            _mark_unavailable()
            return None
        if status == 404 and job_id and not restarted:
            # job 过期 / 结果已被交付过 → 重发一次完整抓取
            restarted, job_id, target = True, None, fresh_target
            continue
        if status == 502 and not retried_502:
            retried_502 = True
            time.sleep(_POLL_INTERVAL_SEC)
            continue
        print(f"[real-browser] 抓取失败（HTTP {status}）", file=sys.stderr)
        return None

    print(f"[real-browser] 超出轮询预算 {wait_sec}s，放弃（任务可能仍在服务端跑）", file=sys.stderr)
    return None

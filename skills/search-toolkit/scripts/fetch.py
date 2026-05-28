#!/usr/bin/env python3
"""URL → markdown / 原文 抓取入口。

CLI: python3 fetch.py <url>

流程：先直连 GET 拿 body + Content-Type → 反爬识别 → 按 Content-Type 判 raw/HTML。
- raw（text/plain、text/markdown、application/json、源码等 / 无 HTML 标签）→ 原文直返
- HTML（text/html）→ 二次送 Jina Reader 渲染
所有请求经 lib/_http（读取/抓取豁免站点调用上限）。

输出 JSON：
- HTML 成功 → { "source": "jina-reader", "url", "markdown", "anonymous", "fallback": null }
- raw 成功  → { "source": "raw", "url", "markdown": <原文>, "fallback": null }
- 被挡       → { "source": null, "url", "markdown": null, "blocked": "anti_bot"|"needs_auth", "on_blocked": "honest"|"collaborate", "fallback": null }
- 无 key / 网络失败 → { "source": null, "url", "markdown": null, "fallback": "WEBFETCH_FALLBACK" }

blocked 两类：
- anti_bot：验证码 / 风控墙（如微信），合规手段过不去
- needs_auth：登录墙 / 付费墙（HTTP 401/403），未来 B-006 远程 browser-host 用登录态会话拿
`on_blocked` 是用户在 limits.yaml 配的策略（honest / collaborate），透传给主 agent 决定下一步。
"""

from __future__ import annotations

import argparse
import sys

from lib import BackendError, emit, jina, config
from lib import _http

# 反爬 / 验证码页强信号短语（大小写不敏感）
_BLOCK_SIGNATURES = (
    "环境异常",
    "完成验证后即可继续访问",
    "去验证",
    "requiring captcha",
    "拖动下方滑块",
    "滑块",
    "captcha",
)
_BLOCK_MAX_LEN = 1500  # 「短内容」阈值：验证墙页都很短，避免误杀正常长文

# 视为 raw（原文直返，不送 Jina Reader）的 Content-Type
_RAW_CTYPES = {
    "text/plain", "text/markdown", "text/x-markdown", "application/json",
    "application/xml", "text/xml", "text/csv", "application/x-yaml",
    "text/yaml", "application/yaml", "text/x-python", "application/javascript",
    "text/javascript",
}
_HTML_CTYPES = {"text/html", "application/xhtml+xml"}
_HTML_TAG_MARKERS = ("<!doctype html", "<html", "<head", "<body")


def _looks_blocked(text: str) -> bool:
    """双条件：短内容 + 命中反爬强信号 → 判反爬墙。"""
    if not text or len(text) > _BLOCK_MAX_LEN:
        return False
    low = text.lower()
    return any(sig.lower() in low for sig in _BLOCK_SIGNATURES)


def _on_blocked_policy() -> str:
    """读用户在 limits.yaml 配的 web_page_fetch.on_blocked（honest / collaborate）。"""
    try:
        limits = config.load_limits() or {}
        pol = ((limits.get("web_page_fetch") or {}).get("on_blocked") or "honest").lower()
        return pol if pol in ("honest", "collaborate") else "honest"
    except Exception:
        return "honest"


def _is_raw_content_type(ctype: str, body: str) -> bool:
    """Content-Type 主导判 raw/HTML；缺失或含糊时按有无 HTML 标签兜底。"""
    if ctype in _HTML_CTYPES:
        return False
    if ctype in _RAW_CTYPES:
        return True
    if ctype.startswith("text/"):  # 其余 text/* 非 html → raw
        return True
    # 含糊（application/octet-stream、空 ctype 等）→ 看有无 HTML 标签
    head = body[:2000].lower()
    return not any(m in head for m in _HTML_TAG_MARKERS)


def _blocked_payload(url: str, reason: str) -> dict:
    return {
        "source": None, "url": url, "markdown": None,
        "blocked": reason, "on_blocked": _on_blocked_policy(), "fallback": None,
    }


def _fetch_one(url: str) -> dict:
    """抓单个 URL，返回结果 dict（不打印）。供单抓与并发 batch 共用。"""
    # 1. 直连 GET（豁免站点调用上限），拿 body + Content-Type
    try:
        body, ctype = _http.request_text_meta(
            "GET", url, backend="fetch", endpoint="direct", timeout=30, cap_exempt=True,
        )
    except BackendError as e:
        if e.http_status in (401, 403):
            print(f"[fetch] 直连 {e.http_status}，判 needs_auth：{url}", file=sys.stderr)
            return _blocked_payload(url, "needs_auth")
        print(f"[fetch] 直连失败：{e}", file=sys.stderr)
        return {"source": None, "url": url, "markdown": None, "fallback": "WEBFETCH_FALLBACK"}

    # 2. 反爬识别（直连 body）
    if _looks_blocked(body):
        print(f"[fetch] 直连命中反爬墙：{url}", file=sys.stderr)
        return _blocked_payload(url, "anti_bot")

    # 3. raw → 原文直返
    if _is_raw_content_type(ctype, body):
        return {"source": "raw", "url": url, "markdown": body, "fallback": None}

    # 4. HTML → 二次送 Jina Reader 渲染（更干净、处理 JS）
    try:
        data = jina.fetch(url)
    except BackendError as e:
        print(f"[fetch] jina-reader 失败：{e}", file=sys.stderr)
        return {"source": None, "url": url, "markdown": None, "fallback": "WEBFETCH_FALLBACK"}

    # 5. Jina 渲染结果也查反爬（微信经 Jina 同样是验证页）
    if _looks_blocked(data.get("markdown", "") or ""):
        print(f"[fetch] jina-reader 命中反爬墙：{url}", file=sys.stderr)
        return _blocked_payload(url, "anti_bot")

    return {"source": "jina-reader", **data, "fallback": None}


def _fetch_concurrency() -> int:
    """并发抓取的 worker 数。默认 2（贴 Jina 免费档「2 concurrent」上限）。

    Jina 速率限制按 API key 计：Free 2 并发 / Paid 50 / Premium 500。免费档并发是
    瓶颈（非 RPM），设 >2 会撞并发限吃 429。Paid 用户可在 limits.yaml 调高。
    """
    try:
        limits = config.load_limits() or {}
        v = int((limits.get("fast_search") or {}).get("fetch_concurrency", 2))
        return max(1, v)
    except Exception:
        return 2


def main() -> int:
    ap = argparse.ArgumentParser(description="Search Crew URL 抓取（支持多 URL 并发）")
    ap.add_argument("urls", nargs="+", help="一个或多个 URL；多个时并发抓取，输出 JSON 数组")
    args = ap.parse_args()

    # 单 URL → 单对象（向后兼容）；多 URL → JSON 数组，按输入顺序，并发抓
    if len(args.urls) == 1:
        emit(_fetch_one(args.urls[0]))
        return 0

    import concurrent.futures
    workers = min(_fetch_concurrency(), len(args.urls))
    results: list[dict | None] = [None] * len(args.urls)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_fetch_one, u): i for i, u in enumerate(args.urls)}
        for fut in concurrent.futures.as_completed(futs):
            i = futs[fut]
            try:
                results[i] = fut.result()
            except Exception as e:  # 单条异常不拖垮整批
                results[i] = {"source": None, "url": args.urls[i], "markdown": None,
                              "fallback": "WEBFETCH_FALLBACK", "error": str(e)}
    emit(results)  # type: ignore[arg-type]
    return 0


if __name__ == "__main__":
    sys.exit(main())

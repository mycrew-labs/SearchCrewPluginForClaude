#!/usr/bin/env python3
"""URL → markdown / 原文 抓取入口。

CLI: python3 fetch.py [--real-browser] <url> [<url>...]

流程：先直连 GET 拿 body + Content-Type → 反爬识别 → 按 Content-Type 判 raw/HTML。
- raw（text/plain、text/markdown、application/json、源码等 / 无 HTML 标签）→ 原文直返
- HTML（text/html）→ 二次送 Jina Reader 渲染
所有请求经 lib/_http（读取/抓取豁免站点调用上限）。

`--real-browser`（默认关）：允许升级到 universal-page-fetcher（真实已登录浏览器执行端，
见 lib/real_browser.py）。两类场景才升级：
- 域名直达：host 命中 limits.yaml `web_page_fetch.real_browser.direct_domains`
  （已知普通链「成功但残缺」的虚拟滚动 / 强风控站）→ 跳过普通链直接升级；
  升级失败回落普通链，成功输出附 warning 提示内容可能不完整
- 被挡升级：anti_bot / needs_auth / 抓取链失败时先试升级层，仍失败才按原样输出
任何调用方按需带本开关（需登录态 / 虚拟滚动长文档 / 被挡才有必要）；批量抓取只对
确有需要的 URL 开——执行端并发上限 10、单任务分钟级，整批盲目开启会打爆它。

输出 JSON：
- HTML 成功 → { "source": "jina-reader", "url", "markdown", "anonymous", "fallback": null }
- raw 成功  → { "source": "raw", "url", "markdown": <原文>, "fallback": null }
- 升级成功  → { "source": "universal-page-fetcher", "url", "title", "markdown", "coverage", "fallback": null }
- 被挡       → { "source": null, "url", "markdown": null, "blocked": "anti_bot"|"needs_auth", "on_blocked": "honest"|"collaborate", "fallback": null }
- 无 key / 网络失败 → { "source": null, "url", "markdown": null, "fallback": "WEBFETCH_FALLBACK" }
- 直达升级失败回落普通链的成功输出，额外带
  "warning": "real_browser_unavailable_content_may_be_incomplete"

blocked 两类：
- anti_bot：验证码 / 风控墙，合规手段过不去（升级层用真实浏览器登录态多数能过）
- needs_auth：登录墙 / 付费墙（HTTP 401/403）
`on_blocked` 是用户在 limits.yaml 配的策略（honest / collaborate），透传给主 agent 决定下一步。
"""

from __future__ import annotations

import argparse
import sys

from lib import BackendError, emit, jina, config, real_browser, fetch_routing
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

# 域名直达的「站点 → 抓取能力」mapping 收敛到 lib/fetch_routing（fetch.py 与拦截 hook 共用）。
_DEFAULT_RB_WAIT_SEC = 480
_RB_WARNING = "real_browser_unavailable_content_may_be_incomplete"


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


def _rb_wait_sec() -> int:
    """读 limits.yaml web_page_fetch.real_browser.wait_sec，缺失回落内置默认。"""
    try:
        limits = config.load_limits() or {}
        rb = ((limits.get("web_page_fetch") or {}).get("real_browser")) or {}
        return max(30, int(rb.get("wait_sec", _DEFAULT_RB_WAIT_SEC)))
    except Exception:
        return _DEFAULT_RB_WAIT_SEC


def _matches_direct_domain(url: str) -> bool:
    """host 命中 mapping 中 capability=real-browser 的条目 → 直达升级。

    mapping（站点 → 抓取能力）由 lib/fetch_routing 从行式清单 site-fetch.txt 统一加载，
    与拦截 hook 共用同一份事实源。
    """
    try:
        mapping = fetch_routing.active_mapping()
    except Exception:
        mapping = None
    return fetch_routing.capability_for_url(url, mapping) == fetch_routing.REAL_BROWSER


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


def _try_real_browser(url: str) -> dict | None:
    """经 universal-page-fetcher 升级抓取；任何失败返回 None（回落交给调用方）。"""
    wait_sec = _rb_wait_sec()
    data = real_browser.fetch_page(url, wait_sec)
    if data is None:
        return None
    return {
        "source": "universal-page-fetcher", "url": url,
        "title": data.get("title"), "markdown": data["markdown"],
        "coverage": data.get("coverage"), "fallback": None,
    }


def _fetch_one(url: str, allow_real_browser: bool = False) -> dict:
    """抓单个 URL，返回结果 dict（不打印）。供单抓与并发 batch 共用。"""
    rb_attempted = False
    warning: str | None = None

    # 0. 域名直达：已知普通链「成功但残缺」的站点，开关开启时直接升级
    if allow_real_browser and _matches_direct_domain(url):
        rb_attempted = True
        res = _try_real_browser(url)
        if res is not None:
            return res
        # 直达失败回落普通链——拿到的内容可能不完整，成功输出必须带 warning，
        # 不静默装完整（要么抓全，要么明确告知）
        warning = _RB_WARNING
        print(f"[fetch] 直达升级失败，回落普通链（内容可能不完整）：{url}", file=sys.stderr)

    def _upgrade() -> dict | None:
        """被挡 / 抓取链失败时的升级尝试。每 URL 最多升级一次。"""
        nonlocal rb_attempted
        if not allow_real_browser or rb_attempted:
            return None
        rb_attempted = True
        return _try_real_browser(url)

    def _finish(payload: dict) -> dict:
        if warning:
            payload["warning"] = warning
        return payload

    # 1. 直连 GET（豁免站点调用上限），拿 body + Content-Type
    try:
        body, ctype = _http.request_text_meta(
            "GET", url, backend="fetch", endpoint="direct", timeout=30, cap_exempt=True,
        )
    except BackendError as e:
        if e.http_status in (401, 403):
            # 登录/付费墙：先试真实浏览器登录态，拿不到才判 needs_auth
            print(f"[fetch] 直连 {e.http_status}，判 needs_auth：{url}", file=sys.stderr)
            return _upgrade() or _blocked_payload(url, "needs_auth")
        print(f"[fetch] 直连失败：{e}", file=sys.stderr)
        return _upgrade() or _finish({"source": None, "url": url, "markdown": None, "fallback": "WEBFETCH_FALLBACK"})

    # 2. 反爬识别（直连 body）
    if _looks_blocked(body):
        print(f"[fetch] 直连命中反爬墙：{url}", file=sys.stderr)
        return _upgrade() or _blocked_payload(url, "anti_bot")

    # 3. raw → 原文直返
    if _is_raw_content_type(ctype, body):
        return _finish({"source": "raw", "url": url, "markdown": body, "fallback": None})

    # 4. HTML 渲染链：jina-reader →（--real-browser 升级）→ Claude WebFetch
    try:
        data = jina.fetch(url)
    except BackendError as e:
        print(f"[fetch] jina-reader 失败：{e}", file=sys.stderr)
        return _upgrade() or _finish({"source": None, "url": url, "markdown": None, "fallback": "WEBFETCH_FALLBACK"})

    # 5. Jina 渲染结果也查反爬（微信经 Jina 同样是验证页）
    if _looks_blocked(data.get("markdown", "") or ""):
        print(f"[fetch] jina-reader 命中反爬墙：{url}", file=sys.stderr)
        return _upgrade() or _blocked_payload(url, "anti_bot")

    return _finish({"source": "jina-reader", **data, "fallback": None})


def _fetch_concurrency() -> int:
    """并发抓取的 worker 数。默认 5。

    Jina Reader（r.jina.ai）免费 key 500 RPM（≈8 req/s），并发非主要瓶颈；官方 FAQ
    另有一句笼统的「Free 2 concurrent」但未明确卡 Reader，社区工具默认 5 可用，故取 5。
    频繁 429 可在 limits.yaml 调低；Paid（50）/ Premium（500）可调高。
    """
    try:
        limits = config.load_limits() or {}
        v = int((limits.get("fast_search") or {}).get("fetch_concurrency", 5))
        return max(1, v)
    except Exception:
        return 5


def main() -> int:
    ap = argparse.ArgumentParser(description="Search Crew URL 抓取（支持多 URL 并发）")
    ap.add_argument("urls", nargs="+", help="一个或多个 URL；多个时并发抓取，输出 JSON 数组")
    ap.add_argument(
        "--real-browser", action="store_true",
        help="允许升级到 universal-page-fetcher（真实已登录浏览器执行端）；"
             "需登录态 / 虚拟滚动 / 被挡的页面才有必要，批量抓取只对确有需要的 URL 开",
    )
    args = ap.parse_args()

    # 单 URL → 单对象（向后兼容）；多 URL → JSON 数组，按输入顺序，并发抓
    if len(args.urls) == 1:
        emit(_fetch_one(args.urls[0], allow_real_browser=args.real_browser))
        return 0

    import concurrent.futures
    workers = min(_fetch_concurrency(), len(args.urls))
    results: list[dict | None] = [None] * len(args.urls)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_fetch_one, u, args.real_browser): i for i, u in enumerate(args.urls)}
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

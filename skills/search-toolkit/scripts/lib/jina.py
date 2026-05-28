"""Jina AI Search + Reader 封装。

- Search: https://s.jina.ai/?q=<query>
- Reader: https://r.jina.ai/<url>

无 key 时 Reader 也可匿名（限流较紧），Search 需要 key。
"""

from __future__ import annotations

from typing import Any

from . import BackendError, env, normalize_result
from . import _http

SEARCH_ENDPOINT = "https://s.jina.ai/"
READER_ENDPOINT = "https://r.jina.ai/"
BACKEND = "jina"


def is_available_search() -> bool:
    return env("JINA_API_KEY") is not None


def is_available_reader() -> bool:
    return True


def search(
    query: str,
    *,
    max_results: int = 10,
    language: str | None = None,
    include_content: bool = False,
) -> list[dict[str, Any]]:
    """通用搜索。

    `include_content=True` 时不加 `X-Respond-With: no-content`，让 s.jina.ai 一次返回
    每条结果的正文（省掉随后逐页 fetch 的 round-trip），正文放进结果的 `content` 字段。
    默认 False（只回链接 + 摘要，轻量，调用方按需再选择性 fetch）。
    """
    api_key = env("JINA_API_KEY")
    if not api_key:
        raise BackendError(BACKEND, "缺少 JINA_API_KEY")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    if not include_content:
        headers["X-Respond-With"] = "no-content"
    if language:
        headers["X-Locale"] = language

    params = {"q": query, "count": max_results}
    data = _http.request_json(
        "GET",
        SEARCH_ENDPOINT,
        backend=BACKEND,
        endpoint="search",
        headers=headers,
        params=params,
        query=query,
    )

    items = (data or {}).get("data") or []
    results = []
    for it in items[:max_results]:
        content = it.get("content") or ""
        snippet = it.get("description", "") or content[:280]
        r = normalize_result(
            title=it.get("title", ""),
            url=it.get("url", ""),
            snippet=snippet,
            source="jina-search",
        )
        if include_content and content:
            r["content"] = content
        results.append(r)
    return results


def fetch(url: str) -> dict[str, Any]:
    headers = {"Accept": "text/markdown"}
    api_key = env("JINA_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    text = _http.request_text(
        "GET",
        READER_ENDPOINT + url,
        backend=BACKEND,
        endpoint="reader",
        headers=headers,
        timeout=60,
        cap_exempt=True,  # 读取/抓取豁免站点调用上限（上限只管搜索源）
    )
    return {
        "url": url,
        "markdown": text,
        "source": "jina-reader",
        "anonymous": api_key is None,
    }

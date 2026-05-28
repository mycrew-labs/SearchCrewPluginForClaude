"""博查（Bocha）Web Search API 封装。

中文网页搜索能力强，补 jina/serper/AI 几家中文偏弱的短板。
端点：POST https://api.bochaai.com/v1/web-search
返回 webPages.value[]：name / url / snippet / summary(summary=true 时较长摘要) /
siteName / datePublished —— 给 snippet + summary，不返全文 content（全文需另抓）。
"""

from __future__ import annotations

from typing import Any

from . import BackendError, env, normalize_result
from . import _http

ENDPOINT = "https://api.bochaai.com/v1/web-search"
BACKEND = "bocha"


def is_available() -> bool:
    return env("BOCHA_API_KEY") is not None


def search(query: str, *, max_results: int = 10, language: str | None = None) -> list[dict[str, Any]]:
    api_key = env("BOCHA_API_KEY")
    if not api_key:
        raise BackendError(BACKEND, "缺少 BOCHA_API_KEY")

    body = {
        "query": query,
        "count": max(1, min(max_results, 50)),  # bocha 上限 50
        "summary": True,                          # 要较长摘要，比 snippet 信息多
        "freshness": "noLimit",
    }
    headers = {"Authorization": f"Bearer {api_key}"}

    data = _http.request_json(
        "POST",
        ENDPOINT,
        backend=BACKEND,
        endpoint="search",
        headers=headers,
        json_body=body,
        query=query,
    )

    # 响应结构：{code, log_id, msg, data:{webPages:{value:[...]}}}
    payload = (data or {}).get("data") or {}
    items = ((payload.get("webPages") or {}).get("value")) or []
    results = []
    for it in items[:max_results]:
        # summary 比 snippet 信息更全，优先用 summary
        snippet = (it.get("summary") or "").strip() or (it.get("snippet") or "")
        results.append(
            normalize_result(
                title=it.get("name", ""),
                url=it.get("url", ""),
                snippet=snippet,
                source="bocha",
                date=it.get("datePublished") or it.get("dateLastCrawled"),
                site=it.get("siteName"),
            )
        )
    return results

"""AI 综述 backend 公共结构。

三家（grok / gemini / doubao）的请求 / 响应字段各不一样，但对调用方暴露的形态
统一为：

    {
      "backend": "grok" | "gemini" | "doubao",
      "summary": str,        # AI 综述正文
      "citations": [         # 引用源
        {"url": str, "title": str, "snippet": str},
      ],
      "results": [...],      # 兼容 jina/serper 的 normalize_result schema，从 citations 派生
    }

各 backend 文件只负责构造请求 + 解析响应到这个统一结构。
"""

from __future__ import annotations

from typing import Any

from .. import normalize_result


def parse_responses_api(data: dict[str, Any], backend: str) -> tuple[str, list[dict[str, Any]]]:
    """解析 OpenAI 风格 Responses API（xAI / 火山方舟共用）。

    结构：`output[]` 数组，元素 type 含 reasoning / web_search_call / message。
    最终答案在 type=message 的 `content[]`（type=output_text）里：
    - `text` 是综述正文
    - `annotations[]`（type=url_citation）是引用源，每条含 url / title

    返回 (summary, citations)。找不到 message 时抛 BackendError。
    """
    from .. import BackendError  # noqa: PLC0415  避免顶层循环依赖

    outputs = (data or {}).get("output") or []
    summary_parts: list[str] = []
    citations: list[dict[str, Any]] = []
    found_message = False
    for item in outputs:
        if item.get("type") != "message":
            continue
        found_message = True
        for c in item.get("content") or []:
            if c.get("type") not in ("output_text", "text"):
                continue
            summary_parts.append(c.get("text", "") or "")
            for ann in c.get("annotations") or []:
                if ann.get("type") != "url_citation":
                    continue
                url = ann.get("url") or ""
                if url:
                    cit = {
                        "url": url,
                        "title": ann.get("title", ""),
                        "snippet": ann.get("snippet", "") or ann.get("content", ""),
                    }
                    # 注：grok 的 url_citation 虽带 start_index/end_index，但 grok 的 summary
                    # 正文里**已内联** `[n]` 标记（annotation.title 即该编号），故这里不另存偏移、
                    # 不让 ai_search 再插一遍（会重复）。doubao 无偏移、无内联标记，只带富元数据。
                    for k in ("site_name", "publish_time"):
                        if ann.get(k):
                            cit[k] = ann.get(k)
                    citations.append(cit)
    if not found_message:
        raise BackendError(backend, f"Responses API 无 message 输出: {str(data)[:200]}")
    return "".join(summary_parts), citations


def make_envelope(
    *,
    backend: str,
    summary: str,
    citations: list[dict[str, Any]],
) -> dict[str, Any]:
    """统一组装返回结构。citations[*] MUST 至少含 url；title / snippet 可缺。"""
    norm_citations: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for c in citations:
        url = (c.get("url") or "").strip()
        if not url:
            continue
        title = (c.get("title") or "").strip() or url
        snippet = (c.get("snippet") or "").strip()
        nc: dict[str, Any] = {"url": url, "title": title, "snippet": snippet}
        # 透传可用于脚注的字符偏移（grok / gemini）与富元数据（doubao），别丢
        for k in ("start_index", "end_index", "site_name", "publish_time"):
            if c.get(k) is not None:
                nc[k] = c[k]
        norm_citations.append(nc)
        results.append(
            normalize_result(
                title=title,
                url=url,
                snippet=snippet,
                source=f"{backend}-citation",
            )
        )
    return {
        "backend": backend,
        "summary": (summary or "").strip(),
        "citations": norm_citations,
        "results": results,
    }

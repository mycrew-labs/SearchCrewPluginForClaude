"""Google（Gemini）Search Grounding backend。

文档：
- generateContent API: https://ai.google.dev/api/generate-content
- Search Grounding: https://ai.google.dev/gemini-api/docs/grounding

最后验证：2026-05-23

请求 = generateContent + `tools: [{google_search: {}}]`；响应 `candidates[].groundingMetadata.groundingChunks[].web.uri`
含引用源 URL。

model 不在代码 hardcode：由调用方（search.py）从 routing.yaml ai_summary.models.gemini
按 subagent 分层（fast/deep）解析后传入。
"""

from __future__ import annotations

from typing import Any

from .. import BackendError, env
from .. import _http
from .ai_common import make_envelope

BACKEND = "gemini"
API_KEY_ENV = "GEMINI_API_KEY"
ENDPOINT_TPL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def is_available() -> bool:
    return env(API_KEY_ENV) is not None


def search(query: str, *, max_results: int = 10, model: str | None = None) -> dict[str, Any]:
    api_key = env(API_KEY_ENV)
    if not api_key:
        raise BackendError(BACKEND, f"缺少 {API_KEY_ENV}")
    if not model:
        raise BackendError(BACKEND, "未配置 model，请在 routing.yaml ai_summary.models.gemini 设置 fast/deep")

    body = {
        "contents": [{"role": "user", "parts": [{"text": query}]}],
        "tools": [{"google_search": {}}],
        "systemInstruction": {
            "parts": [{"text": "你是一个调研助手。基于 Google Search Grounding 给出综述。"}]
        },
    }
    headers = {"x-goog-api-key": api_key}

    data = _http.request_json(
        "POST",
        ENDPOINT_TPL.format(model=model),
        backend=BACKEND,
        endpoint="generateContent",
        headers=headers,
        json_body=body,
        timeout=60,
        query=query,
    )

    try:
        candidates = (data or {}).get("candidates") or []
        if not candidates:
            raise BackendError(BACKEND, f"gemini 返回无 candidates: {str(data)[:200]}")
        cand = candidates[0]
        parts = (cand.get("content") or {}).get("parts") or []
        summary = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
        grounding = cand.get("groundingMetadata") or cand.get("grounding_metadata") or {}
        chunks = grounding.get("groundingChunks") or grounding.get("grounding_chunks") or []
        # groundingSupports：每段正文 → 支撑它的 chunk 下标 + 段末偏移（实测有）。
        # 据此给每个 chunk 算一个 end_index（取引用它的最后一段的段末位置），用于插脚注。
        supports = grounding.get("groundingSupports") or grounding.get("grounding_supports") or []
        chunk_end: dict[int, int] = {}
        for sup in supports:
            seg = sup.get("segment") or {}
            end = seg.get("endIndex")
            if end is None:
                continue
            for ci in (sup.get("groundingChunkIndices") or sup.get("grounding_chunk_indices") or []):
                if isinstance(ci, int):
                    chunk_end[ci] = max(chunk_end.get(ci, 0), end)
        citations = []
        for i, ch in enumerate(chunks[:max_results]):
            web = ch.get("web") or {}
            url = web.get("uri") or web.get("url") or ""
            if not url:
                continue
            cit: dict[str, Any] = {"url": url, "title": web.get("title", ""), "snippet": ""}
            if i in chunk_end:
                cit["end_index"] = chunk_end[i]
            citations.append(cit)
    except BackendError:
        raise
    except Exception as e:
        raise BackendError(BACKEND, f"gemini 响应解析失败: {e}") from e

    return make_envelope(backend=BACKEND, summary=summary, citations=citations)

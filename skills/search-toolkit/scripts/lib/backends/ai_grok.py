"""xAI（Grok）Agent Tools API（web_search）backend。

文档：
- Tools Overview: https://docs.x.ai/docs/guides/tools/overview
- Web Search: https://docs.x.ai/developers/tools/web-search

最后验证：2026-05-23

注意：旧 Live Search（chat/completions + search_parameters）已于 2026-01-12 废弃
（返回 HTTP 410），现统一走 Responses API（/v1/responses）+ 内置 web_search tool。
请求用 `input` 数组，响应在 output[] 的 message 项里（content[].text + annotations[]）。

model 不在代码 hardcode：由调用方（search.py）从 routing.yaml ai_summary.models.grok
按 subagent 分层（fast/deep）解析后传入；reasoning_effort 也由同一配置透传。
"""

from __future__ import annotations

from typing import Any

from .. import BackendError, env
from .. import _http
from .ai_common import make_envelope, parse_responses_api

ENDPOINT = "https://api.x.ai/v1/responses"
BACKEND = "grok"
API_KEY_ENV = "GROK_API_KEY"


def is_available() -> bool:
    return env(API_KEY_ENV) is not None


def search(
    query: str,
    *,
    max_results: int = 10,
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> dict[str, Any]:
    api_key = env(API_KEY_ENV)
    if not api_key:
        raise BackendError(BACKEND, f"缺少 {API_KEY_ENV}")
    if not model:
        raise BackendError(BACKEND, "未配置 model，请在 routing.yaml ai_summary.models.grok 设置 fast/deep")

    body = {
        "model": model,
        "input": [{"role": "user", "content": query}],
        "tools": [{"type": "web_search"}, {"type": "x_search"}],
    }
    if reasoning_effort:
        body["reasoning"] = {"effort": reasoning_effort}
    headers = {"Authorization": f"Bearer {api_key}"}

    data = _http.request_json(
        "POST",
        ENDPOINT,
        backend=BACKEND,
        endpoint="responses",
        headers=headers,
        json_body=body,
        timeout=90,
        query=query,
    )

    try:
        summary, citations = parse_responses_api(data, BACKEND)
    except BackendError:
        raise
    except Exception as e:
        raise BackendError(BACKEND, f"grok 响应解析失败: {e}") from e

    return make_envelope(backend=BACKEND, summary=summary, citations=citations[:max_results] if max_results else citations)

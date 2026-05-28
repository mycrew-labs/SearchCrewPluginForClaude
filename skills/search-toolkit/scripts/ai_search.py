#!/usr/bin/env python3
"""AI 综述快答（/search-fast 的后端，主 agent 直连）。

一次 AI 综述调用拿"现成答案"——不派 subagent、不产结构化文件。AI 源按语言/语境选
（中文→doubao、英文舆论→grok、全球综述→gemini；沿用 routing.yaml selection_order），
fast 档 model。

CLI: python3 ai_search.py --query <q> [--max-results N] [--ai-backend ...] [--model ...]

输出 JSON：
- 成功 → { "backend": "...", "summary": "...", "citations": [...], "fallback": null }
- 无可用 AI 源 → { "backend": null, "summary": null, "fallback": "WEBSEARCH_FALLBACK" }
  （主 agent 收到后回落普通搜索 / 内置 WebSearch）
"""

from __future__ import annotations

import argparse
import re
import sys

from lib import BackendError, emit, ai_summary
from lib import pricing

_CJK_RE = re.compile(r"[一-鿿]")
# AI backend → 其打点 endpoint（用于 cost 估算）
_ENDPOINT = {"grok": "responses", "doubao": "responses", "gemini": "generateContent"}


def _cost_line(backend: str) -> str:
    """本次快答一行 cost——/search-fast 不走 finalize_usage，由这里自报。"""
    cost, _src = pricing.estimate(backend, _ENDPOINT.get(backend, "responses"), 1)
    amount = cost if isinstance(cost, (int, float)) else 0.0
    return f"📊 本次估算 ~${amount:.4f} USD（1 次调用 · {backend}）"


def _render_citations(summary: str, citations: list) -> tuple[str, list, bool]:
    """渲染逐条来源（按 backend 实际能力）。

    - citations 带 `end_index`（gemini grounding 段偏移）→ 在 summary 对应位置插 `[n]` 标记。
    - grok：summary 正文已内联 `[n]`（无 end_index），不重复插，直接沿用。
    - doubao：无偏移、无内联标记 → 正文不动，只给来源列表。

    返回 (summary_cited, 编号来源列表 sources, has_footnotes)。has_footnotes = 正文里是否
    存在 `[n]` 标记（gemini 插入的或 grok 原生的），用于命令判断是否逐条可点。不伪造偏移。
    """
    from collections import defaultdict

    sources, by_pos = [], defaultdict(list)
    n = 0
    for c in citations or []:
        if not isinstance(c, dict):
            continue
        n += 1
        src = {"n": n, "url": c.get("url", ""), "title": c.get("title", "")}
        for k in ("site_name", "publish_time"):
            if c.get(k):
                src[k] = c[k]
        sources.append(src)
        ei = c.get("end_index")
        if isinstance(ei, int) and 0 <= ei <= len(summary):
            by_pos[ei].append(n)

    cited = summary
    for pos in sorted(by_pos, reverse=True):  # 倒序插入，保持前面偏移不失效
        marker = "".join(f"[{m}]" for m in sorted(set(by_pos[pos])))
        p = max(0, min(pos, len(cited)))
        cited = cited[:p] + marker + cited[p:]

    has_footnotes = bool(re.search(r"\[\d+\]", cited))  # gemini 插入的 / grok 原生的
    return cited, sources, has_footnotes


def _lang_preferred_backend(query: str) -> str | None:
    """语言/语境偏好：中文 query 优先 doubao（若可用）；否则交回默认 selection_order。"""
    if _CJK_RE.search(query):
        mod = ai_summary.AI_BACKEND_MODULES.get("doubao")
        if mod and mod.is_available():
            return "doubao"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Search Crew AI 综述快答")
    ap.add_argument("--query", required=True)
    ap.add_argument("--max-results", type=int, default=5)
    ap.add_argument("--ai-backend", choices=["grok", "gemini", "doubao"], default=None,
                    help="显式指定 AI 源；默认按语言/语境 + selection_order 选")
    ap.add_argument("--model", default=None, help="显式覆盖 model（默认 fast 档）")
    args = ap.parse_args()

    explicit = args.ai_backend or _lang_preferred_backend(args.query)
    picked = ai_summary.pick_backend(explicit)
    if not picked:
        # 全缺 key / ai_summary 未启用 → 让主 agent 回落普通搜索
        print("[ai_search] 无可用 AI 综述源（key 缺或 ai_summary 未启用），回落普通搜索", file=sys.stderr)
        emit({"backend": None, "summary": None, "citations": [], "fallback": "WEBSEARCH_FALLBACK",
              "calls": 0, "cost_line": None})
        return 0

    model = ai_summary.resolve_model(picked, "fast", args.model)
    try:
        out = ai_summary.run_ai(picked, args.query, args.max_results, model)
    except BackendError as e:
        print(f"[ai_search] AI 源 {picked} 调用失败：{e}，回落普通搜索", file=sys.stderr)
        emit({"backend": None, "summary": None, "citations": [], "fallback": "WEBSEARCH_FALLBACK",
              "calls": 0, "cost_line": None})
        return 0

    # 按 backend 引用能力渲染脚注：grok/gemini 有偏移 → 插 [n]；doubao 无偏移 → 只给来源列表
    summary = out.get("summary", "")
    citations = out.get("citations", [])
    summary_cited, sources, has_footnotes = _render_citations(summary, citations)

    # /search-fast 不走 run 目录 + finalize_usage：cost 一行由本脚本自报；
    # 调用已经过 _http 进永久统一日志 calls.jsonl（usage.py 查历史可见）。
    emit({
        "backend": out["backend"],
        "summary": summary,
        "summary_cited": summary_cited,
        "has_footnotes": has_footnotes,
        "sources": sources,
        "citations": citations,
        "calls": 1,
        "cost_line": _cost_line(out["backend"]),
        "fallback": None,
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())

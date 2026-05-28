#!/usr/bin/env python3
"""通用搜索入口。

CLI:
  python3 search.py --query <q> [--max-results N] [--language zh-cn]
                    [--prefer jina|serper|ai] [--ai-backend grok|gemini|doubao]
                    [--tier fast|deep] [--model <id>]

输出 JSON 到 stdout：
- 成功 → { "backend": "...", "results": [...], "summary": "...", "fallback": null }
  （summary 仅在 backend 是 AI 综述时出现；citations 走 results 派生）
- 无可用 backend → { "results": [], "fallback": "WEBSEARCH_FALLBACK" }

AI 综述 backend 的 model 不在代码 hardcode：从 routing.yaml ai_summary.models.<backend>
按 tier（fast-search→fast / 其他→deep）解析；可用 --model 显式覆盖。
"""

from __future__ import annotations

import argparse
import sys

from lib import BackendError, emit, config, jina, serper, runtime
from lib.backends import ai_grok, ai_gemini, ai_doubao

AI_BACKEND_MODULES = {
    "grok": ai_grok,
    "gemini": ai_gemini,
    "doubao": ai_doubao,
}
_DEFAULT_SELECTION_ORDER = ["grok", "doubao", "gemini"]


def _ai_summary_cfg() -> dict:
    routing = config.load_routing() or {}
    return routing.get("ai_summary") or {}


def _pick_ai_backend(explicit: str | None) -> str | None:
    """按 selection_order + 可用性挑一个 AI backend。返回 backend 名或 None。"""
    if explicit:
        mod = AI_BACKEND_MODULES.get(explicit)
        return explicit if mod and mod.is_available() else None

    cfg = _ai_summary_cfg()
    if not cfg.get("enabled", True):
        return None
    order = cfg.get("selection_order") or _DEFAULT_SELECTION_ORDER
    for name in order:
        mod = AI_BACKEND_MODULES.get(name)
        if mod and mod.is_available():
            return name
    return None


def _resolve_tier(explicit: str | None) -> str:
    """tier 来源：--tier 显式 > subagent 名（含 'fast' → fast）> deep。"""
    if explicit:
        return explicit
    sub = (runtime.current_subagent() or "").lower()
    return "fast" if "fast" in sub else "deep"


def _resolve_model(backend_name: str, tier: str, explicit_model: str | None) -> str | None:
    """model 来源：--model 显式 > routing.yaml ai_summary.models.<backend>.<tier> > 同 backend 另一档。"""
    if explicit_model:
        return explicit_model
    models = (_ai_summary_cfg().get("models") or {}).get(backend_name) or {}
    return models.get(tier) or models.get("deep") or models.get("fast")


def _run_ai(backend_name: str, query: str, max_results: int, model: str | None) -> dict:
    mod = AI_BACKEND_MODULES[backend_name]
    envelope = mod.search(query, max_results=max_results, model=model)
    return {
        "backend": envelope["backend"],
        "summary": envelope.get("summary", ""),
        "citations": envelope.get("citations", []),
        "results": envelope.get("results", []),
        "fallback": None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Search Crew 通用搜索入口")
    ap.add_argument("--query", required=True)
    ap.add_argument("--max-results", type=int, default=10)
    ap.add_argument("--language", default=None, help="zh / zh-cn / en / en-us")
    ap.add_argument("--prefer", choices=["jina", "serper", "ai"], default=None)
    ap.add_argument(
        "--ai-backend",
        choices=["grok", "gemini", "doubao"],
        default=None,
        help="显式指定 AI 综述 backend（与 --prefer ai 配合）",
    )
    ap.add_argument("--tier", choices=["fast", "deep"], default=None, help="覆盖 model 档位（默认按 subagent 推断）")
    ap.add_argument("--model", default=None, help="显式覆盖 AI backend model（绕过 routing.yaml）")
    args = ap.parse_args()

    # --prefer ai 或 --ai-backend 显式指定 → 优先尝试 AI 综述层
    want_ai = args.prefer == "ai" or args.ai_backend is not None
    if want_ai:
        picked = _pick_ai_backend(args.ai_backend)
        if picked:
            try:
                tier = _resolve_tier(args.tier)
                model = _resolve_model(picked, tier, args.model)
                emit(_run_ai(picked, args.query, args.max_results, model))
                return 0
            except BackendError as e:
                print(f"[search] AI backend {picked} 失败：{e}，回落非 AI 搜索", file=sys.stderr)
        elif args.ai_backend:
            # 用户显式点名了某 AI backend 却挑不中 → 多半缺对应 key / 该层被禁，别静默
            print(
                f"[search] 显式指定的 AI backend '{args.ai_backend}' 不可用"
                f"（缺 {args.ai_backend.upper()}_API_KEY 或 ai_summary 未启用），回落非 AI 搜索",
                file=sys.stderr,
            )
        else:
            print("[search] 无可用 AI 综述 backend（三家 key 均缺或 ai_summary 未启用），回落非 AI 搜索", file=sys.stderr)
        # AI key 全缺 或 AI 调用失败 → 按 fallback_on_no_key 回落
        fallback_be = (_ai_summary_cfg().get("fallback_on_no_key") or "jina").lower()
        if fallback_be == "serper":
            non_ai_order = ["serper", "jina"]
        else:
            non_ai_order = ["jina", "serper"]
    elif args.prefer == "serper":
        non_ai_order = ["serper", "jina"]
    else:
        # 默认 Jina 优先（语义更强）
        non_ai_order = ["jina", "serper"]

    for backend in non_ai_order:
        try:
            if backend == "jina" and jina.is_available_search():
                results = jina.search(args.query, max_results=args.max_results, language=args.language)
                emit({"backend": "jina", "results": results, "fallback": None})
                return 0
            if backend == "serper" and serper.is_available():
                results = serper.search(args.query, max_results=args.max_results, language=args.language)
                emit({"backend": "serper", "results": results, "fallback": None})
                return 0
        except BackendError as e:
            print(f"[search] {backend} 失败：{e}", file=sys.stderr)
            continue

    emit({"backend": None, "results": [], "fallback": "WEBSEARCH_FALLBACK"})
    return 0


if __name__ == "__main__":
    sys.exit(main())

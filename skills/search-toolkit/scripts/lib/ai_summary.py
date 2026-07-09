"""AI 综述层共用逻辑：选源 / 解析模型配置 / 调用。

供 `search.py --prefer ai` 与 `ai_search.py`（/search-fast 快答）共用，避免重复。
AI 源的 model 不在代码 hardcode：从 routing.yaml ai_summary.models.<backend> 按 tier 解析。
"""

from __future__ import annotations

from typing import Any

from . import config, runtime
from .backends import ai_grok, ai_gemini, ai_doubao

AI_BACKEND_MODULES = {
    "grok": ai_grok,
    "gemini": ai_gemini,
    "doubao": ai_doubao,
}
_DEFAULT_SELECTION_ORDER = ["grok", "doubao", "gemini"]
ModelConfig = dict[str, Any]


def ai_summary_cfg() -> dict:
    routing = config.load_routing() or {}
    return routing.get("ai_summary") or {}


def pick_backend(explicit: str | None) -> str | None:
    """按 selection_order + 可用性挑一个 AI backend。返回 backend 名或 None。"""
    if explicit:
        mod = AI_BACKEND_MODULES.get(explicit)
        return explicit if mod and mod.is_available() else None

    cfg = ai_summary_cfg()
    if not cfg.get("enabled", True):
        return None
    order = cfg.get("selection_order") or _DEFAULT_SELECTION_ORDER
    for name in order:
        mod = AI_BACKEND_MODULES.get(name)
        if mod and mod.is_available():
            return name
    return None


def resolve_tier(explicit: str | None) -> str:
    """tier 来源：显式 > subagent 名（含 'fast' → fast）> deep。"""
    if explicit:
        return explicit
    sub = (runtime.current_subagent() or "").lower()
    return "fast" if "fast" in sub else "deep"


def _normalize_model_config(raw: Any) -> ModelConfig:
    """兼容旧字符串格式与新对象格式。"""
    if isinstance(raw, dict):
        return {str(k): v for k, v in raw.items() if v is not None}
    if raw:
        return {"model": raw}
    return {}


def resolve_model_config(backend_name: str, tier: str, explicit_model: str | None) -> ModelConfig:
    """模型配置来源：routing.yaml 档位配置；显式 --model 只覆盖其中的 model。"""
    models = (ai_summary_cfg().get("models") or {}).get(backend_name) or {}
    cfg: ModelConfig = {}
    for key in (tier, "deep", "fast"):
        cfg = _normalize_model_config(models.get(key))
        if cfg:
            break
    if explicit_model:
        cfg["model"] = explicit_model
    return cfg


def resolve_model(backend_name: str, tier: str, explicit_model: str | None) -> str | None:
    """兼容旧调用方：只返回 model 字符串。"""
    return resolve_model_config(backend_name, tier, explicit_model).get("model")


def run_ai(backend_name: str, query: str, max_results: int, model_config: str | ModelConfig | None) -> dict[str, Any]:
    mod = AI_BACKEND_MODULES[backend_name]
    cfg = _normalize_model_config(model_config)
    model = cfg.get("model")
    if backend_name == "grok":
        envelope = mod.search(
            query,
            max_results=max_results,
            model=model,
            reasoning_effort=cfg.get("reasoning_effort"),
        )
    else:
        envelope = mod.search(query, max_results=max_results, model=model)
    return {
        "backend": envelope["backend"],
        "summary": envelope.get("summary", ""),
        "citations": envelope.get("citations", []),
        "results": envelope.get("results", []),
        "fallback": None,
    }

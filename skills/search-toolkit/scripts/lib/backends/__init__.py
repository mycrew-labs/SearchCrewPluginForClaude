"""AI 综述 backend 子包：grok / gemini / doubao（按品牌命名）。

每个 backend 模块导出 `BACKEND` / `is_available()` / `search(...)`，与顶层
lib/jina.py、lib/serper.py 保持一致的 backend 接口约定。model 与后端特定选项不在代码
hardcode，由调用方从 routing.yaml ai_summary.models 按 subagent 分层解析后传入。

- grok：xAI Agent Tools API（web_search + x_search），key=GROK_API_KEY
- gemini：Google Gemini generateContent + google_search grounding，key=GEMINI_API_KEY
- doubao：火山方舟 Responses API（托管 Doubao / DeepSeek / Kimi 等），key=DOUBAO_API_KEY
"""

from . import ai_common, ai_doubao, ai_gemini, ai_grok

__all__ = ["ai_common", "ai_doubao", "ai_gemini", "ai_grok"]

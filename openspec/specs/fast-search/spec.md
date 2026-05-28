# Fast Search

一轮通用快速调研。搜索 + 抓取 + ranking + 摘要，不循环。被主 agent 或 deep-search 派发，每次处理一个子主题。

## Purpose

把"找几个相关 URL 看看说了什么"这类轻量任务从主对话隔离出去，避免污染 context；同时保证产物结构化（关键词 + ranking + INDEX）让上层快速消化。
## Requirements
### Requirement: /search-fast = AI 综述快答（主 agent 直连，无 subagent）
`/search-fast <主题>` SHALL 由主 agent **直接**跑 `ai_search.py`（不派任何 subagent），一次 AI 综述调用拿到 `{summary, citations}` 并呈现给用户。AI 源 MUST 按语言/语境从 grok/gemini/doubao 选一个（中文热点偏 doubao、英文舆论偏 grok、全球综述偏 gemini；沿用 routing.yaml selection_order），用 fast 档 model。命中 ROUTING 硬规则（临床/专利等）时 MUST NOT 用快答，应提示走 site-search/deep。全部 AI key 缺失时回落非 AI 搜索（jina/serper）。产物形态是一段综述 + 引用，**不产结构化文件**（要结构化证据走 deep，内部派 evidence-search）。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-28

#### Scenario: 直连出综述
- **WHEN** 用户 `/search-fast 最近抖音爆火的 AI 应用`（DOUBAO_API_KEY 已配）
- **THEN** 主 agent 直接跑 `ai_search.py`（选 doubao），呈现综述 + citations + 一行 cost，全程不派 subagent

#### Scenario: 不产结构化文件
- **WHEN** `/search-fast` 完成
- **THEN** 产物是综述文本 + 引用，没有 `evidence-search-NNN.md` 那类结构化文件

#### Scenario: AI key 全缺回落
- **WHEN** grok/gemini/doubao key 均未配
- **THEN** `/search-fast` 回落 jina/serper 普通搜索，不报错


---
name: search-fast
description: AI 综述快答——主 agent 直连 ai_search.py，一次 AI 调用拿"现成答案"+引用，秒级返回，不派 subagent、不产结构化文件。
---

## 用户主题

`{{args}}`

## 主 agent 工作流

`/search-fast` = **AI 综述快答**：你（主 agent）**直接**跑 `ai_search.py`，一次 AI 调用拿到一段综述 + 引用，呈现给用户。**不派任何 subagent、不产结构化产物文件**——要逐篇证据 / 结构化产物请走 `/search-deep`（内部派 evidence-search）。

### 1. 造本次 run 目录（隔离打点）

```bash
python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/run_paths.py --new
```

输出一个目录路径，作 `<run_root>`。

### 2. 直连跑 ai_search.py

```bash
SEARCH_CREW_RUN_ROOT=<run_root> python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/ai_search.py --query "{{args}}"
```

- AI 源按语言/语境自动选（中文→doubao、英文舆论→grok、全球综述→gemini）；无需你指定。
- 输出 JSON：`{backend, summary, citations, fallback}`。
- 若返回 `fallback: WEBSEARCH_FALLBACK`（AI key 全缺或调用失败）→ 改用内置 WebSearch，或跑 `search.py --prefer serper` 拿普通结果，照常给用户答。

### 3. 最终回复用户

- **核心结论**：基于 `summary` 用你自己的话呈现，**必须**附 `citations` 里的来源 URL（不编造）。
- **cost 一行**：调 `python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/finalize_usage.py <run_root> --one-line` 拼到末尾。

**不要**写出 `<run_root>` 路径或展开 cost 拆分。

## 何时该升级

- 要逐篇原始证据 / 可循证的结构化产物 → `/search-deep`（内部派 evidence-search 采集）
- 要「对 N 个同类对象跑同一套分析」→ `/search-wide`

## 关键约束

- **直连 ai_search.py，不派 subagent**（这是 /search-fast 与 deep/wide 的本质区别——快答省掉 subagent 开销）
- 命中权威主题（临床 / 专利 / 学术等）时 AI 综述不可靠，提示用户改走 `/search-deep` 或 site-search
- cost 总览只一行

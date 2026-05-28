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

### Requirement: /search-fast 综述按 backend 引用能力渲染逐条来源
`/search-fast` 呈现 AI 综述时 SHALL 尽量让每条结论可回溯到来源。`ai_search.py` MUST 按所用 backend 的实际引用能力分两种渲染：

- **backend 提供字符偏移时**（实测 grok 的 `url_citation.start_index/end_index`、gemini 的 `groundingSupports[].segment` + `groundingChunkIndices`）：MUST 在 summary 对应位置插入 `[n]` 脚注标记，并产出编号来源列表 `[n] <标题> — <url>`，使该条结论可点开核对。
- **backend 不提供偏移时**（实测 doubao 仅给 `url`/`title`/`site_name`/`publish_time`，无偏移）：MUST 回落为「综述 + 末尾富信息来源列表」（带站名 / 时间），MUST NOT 伪造偏移或硬凑逐行映射。

输出 MUST 含 `sources`（编号来源列表）、`summary_cited`（带 `[n]` 标记的正文；grok 沿用其原生内联标记，gemini 按偏移插入，doubao 无标记则等于原文）、`has_footnotes`（正文是否含 `[n]`）。命令呈现 MUST 用之，使用户能逐条（或逐源）核对原始资料。脚注语义是"模型声明引用了该源"，MUST NOT 宣称逐字可考——逐条锚到原文段落是 `/search-deep`（evidence-search anchor）的职责。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-29

#### Scenario: grok / gemini 渲染脚注
- **WHEN** `/search-fast` 用 grok 或 gemini 出综述，且响应含引用偏移
- **THEN** summary 各结论后带 `[n]` 标记，末尾有编号来源列表，`[n]` 可对到具体 URL

#### Scenario: doubao 回落富信息来源列表
- **WHEN** `/search-fast` 用 doubao 出综述（无偏移）
- **THEN** 呈现综述 + 末尾来源列表（含站名 / 标题 / 时间），不伪造逐行脚注

#### Scenario: 不冒充逐字可考
- **WHEN** 用户想逐条锚到原文段落核对
- **THEN** 快答提示这是"带出处的速览"；逐条原文级循证请用 `/search-deep`

### Requirement: /search-fast 默认引擎可由 fast_default 固定
`ai_search.py` 选 AI 源时 MUST 读 `~/.config/search-crew/routing.yaml` 的 `ai_summary.fast_default`：
- 值为具体家（`grok` / `gemini` / `doubao`）且该家可用 → **强制用它，无视语言/语境**。
- 值为 `auto`（默认）、缺失、或指定家不可用 → 回落按语言/语境 + `selection_order` 选（中文偏 doubao、英文偏 grok/gemini）。

用户可在 `/search-skill-setup` 交互选择该默认引擎，由 `seed_user_config.py --set-fast-default` 写入（不手改 active）。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-29

#### Scenario: 固定 gemini
- **WHEN** `ai_summary.fast_default: gemini`，用户 `/search-fast 国产新能源车`（中文）
- **THEN** ai_search 用 gemini（不因中文转 doubao）

#### Scenario: auto 仍按语言
- **WHEN** `fast_default: auto`（或缺失），中文 query
- **THEN** 按现有逻辑优先 doubao

#### Scenario: 指定家不可用时回落
- **WHEN** `fast_default: gemini` 但 `GEMINI_API_KEY` 未配
- **THEN** ai_search 回落语言/语境 + selection_order，不报错


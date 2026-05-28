## ADDED Requirements

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

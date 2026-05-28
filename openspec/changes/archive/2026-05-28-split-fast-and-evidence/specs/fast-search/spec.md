## REMOVED Requirements

### Requirement: fast-search 不做站内精确搜索，不做多轮调研
**Reason**: 结构化采集职责迁往新能力 `evidence-search`。
**Migration**: 见 `evidence-search` 同名需求（行为不变）。

### Requirement: fast-search 产出 ranking + 摘要 + 关键词
**Reason**: 迁往 `evidence-search`。
**Migration**: 见 `evidence-search` 同名需求。

### Requirement: fast-search 在零 key 时 fallback 到 WebSearch
**Reason**: 迁往 `evidence-search`。
**Migration**: 见 `evidence-search` 同名需求。

### Requirement: fast-search 产物文件以 subagent 名字为前缀
**Reason**: 迁往 `evidence-search`（前缀改为 `evidence-search`）。
**Migration**: 见 `evidence-search` 同名需求。

### Requirement: fast-search 触发反例（不应派 fast-search 的场景）
**Reason**: 迁往 `evidence-search`。
**Migration**: 见 `evidence-search` 同名需求。

### Requirement: fast-search 可选用 AI 综述 backend
**Reason**: AI 综述从 fast-search 的"可选第一跳"升为 `/search-fast` 快答的**主路径**；其按语言选 AI 源（中文 doubao / 英文舆论 grok / 全球综述 gemini）的逻辑并入下方新需求。
**Migration**: 见下方「`/search-fast` = AI 综述快答」。

### Requirement: fast-search 查询词构造遵循「主题 + 目标 + 限定条件」
**Reason**: 迁往 `evidence-search`。
**Migration**: 见 `evidence-search` 同名需求。

## ADDED Requirements

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

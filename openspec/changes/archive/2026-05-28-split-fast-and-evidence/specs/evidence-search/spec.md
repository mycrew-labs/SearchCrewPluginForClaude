## ADDED Requirements

### Requirement: evidence-search 不做站内精确搜索，不做多轮调研
evidence-search subagent SHALL 只跑**一轮**通用搜索 + 抓取 + 摘要。MUST NOT 做站内精确搜索（该交给 site-search）。MUST NOT 做多轮跨主题挖掘（该交给 deep-search）。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-28

#### Scenario: 接到任务后只跑一轮
- **WHEN** evidence-search 收到 query
- **THEN** 跑一次搜索 + 抓 top N + 写盘 + 返回；不发起第二轮搜索

#### Scenario: 命中权威主题时返回信号给上级
- **WHEN** evidence-search 发现 query 主题应该走 site-search（如临床 / 专利 / 官方文档）
- **THEN** 返回信号给上级，请上级派 site-search，不自己强行做

### Requirement: evidence-search 中英双语并发，serper 主 jina 备，全挂回落 WebSearch
evidence-search 处理一个查询时 SHALL **同 turn 并发**跑两条 lane：①全球/权威 lane 用 `search.py --prefer serper`（英文查询版本，serper 背靠 Google 较权威），serper 失败时回落 jina（jina 可 `--with-content` 一次带正文）；②中文 lane 用 `search.py --prefer bocha`（中文查询版本）。两 lane 结果 MUST 按 URL 去重后 merge。两 lane 全部失败时 MUST 回落 Claude 内置 WebSearch。serper / bocha 只回 snippet/summary（无全文）时，MUST 对需要全文的 top 结果用 `fetch.py` 并发补抓；jina lane 已带 content 的免抓。

#### Scenario: 中英双语并发
- **WHEN** evidence-search 收到一个查询
- **THEN** 同 turn 并发发起 serper（英文版）+ bocha（中文版）两路搜索，结果按 URL 去重 merge

#### Scenario: serper 失败回落 jina
- **WHEN** serper lane 调用失败
- **THEN** 该 lane 改用 jina（优先 `--with-content`），不影响 bocha lane

#### Scenario: 两 lane 全挂回落 WebSearch
- **WHEN** serper/jina 与 bocha 均不可用
- **THEN** evidence-search 回落 Claude 内置 WebSearch 完成检索

### Requirement: evidence-search 产出 ranking + 摘要 + 关键词
evidence-search MUST 在产物中给每条结果打 ranking 分数（0-10）+ 推荐等级（must-read / should-read / skip-able）+ 关键词清单。这三件事 MUST 在抓取阶段**当下**完成，不允许「先全抓回来后续再补」。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-28

#### Scenario: 单 markdown 头部含关键词
- **WHEN** evidence-search 写 `evidence-search-001.md`
- **THEN** 文件头部 YAML front-matter 含 `url` / `ranking` / `recommended` / `keywords` 四个字段

#### Scenario: INDEX 按 ranking 排序
- **WHEN** evidence-search 写 `INDEX.md`
- **THEN** 子文件列表按 ranking 降序，且每条含简介 + 推荐等级 + 关键词子集

### Requirement: evidence-search 在零 key 时 fallback 到 WebSearch
evidence-search 在 `search.py` 返回 `WEBSEARCH_FALLBACK` 时 MUST 改用 Claude Code 内置 WebSearch；在 `fetch.py` 返回 `WEBFETCH_FALLBACK` 时 MUST 改用 WebFetch。整个流程在零 key 状态下仍能完成。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-28

#### Scenario: 零 key fallback
- **WHEN** 搜索 backend 的 key 均未设置
- **THEN** evidence-search 调 `search.py` 后收到 `WEBSEARCH_FALLBACK` marker，转而调用 WebSearch 完成检索

### Requirement: evidence-search 产物文件以 subagent 名字为前缀
所有 evidence-search 落盘的文件 / 子目录 MUST 以 `evidence-search` 为前缀（`evidence-search-NNN.md` / `evidence-search/`）。混合命名（如 `results-1.md`）禁止。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-28

#### Scenario: 落盘命名
- **WHEN** evidence-search 抓回三个结果
- **THEN** 文件名形如 `evidence-search-001.md`、`evidence-search-002.md`、`evidence-search-003.md`

### Requirement: evidence-search 触发反例（不应派 evidence-search 的场景）
evidence-search agent description 中 MUST 包含「不要因以下情况派 evidence-search」反例清单。反例 MUST 至少覆盖：单条事实查询、已有具体 URL 只需 fetch、需要站内精确搜索（应派 site-search）、需要多轮跨主题挖掘（应派 deep-search）、只想要一口现成答案（应走 `/search-fast` AI 综述快答）。

#### Scenario: agent description 含反例段
- **WHEN** 读取 `agents/evidence-search.md`
- **THEN** 文件存在标题为「## 不要触发本 agent 的场景」（或等义中文）的反例清单段

### Requirement: evidence-search 查询词构造遵循「主题 + 目标 + 限定条件」
evidence-search 在调 search.py 之前 SHALL 把 query 构造成至少含「主题 + 目标 + 限定条件」三要素的形态。MUST NOT 只丢一个单名词到 backend。限定条件 MUST 覆盖至少一项：语言、地区、时间范围、平台范围、输出形式。

#### Scenario: 主题过短时主动补限定条件
- **WHEN** 主 agent 传入 query 仅为「vLLM」
- **THEN** evidence-search 在 prompt 内部把 query 扩成「vLLM 在 2025 年的性能基准对比 + 英文官方源」再传给 backend

# Orchestration

主 agent 接到搜索类需求后的路由、派发、综合、回复闭环。承担循证四步的入口环节与证据传递的最后一棒。

## Purpose

让用户用自然语言（或一个 slash command）启动调研，主 agent 自动判断派哪种 subagent、并行派发、综合产物、给出带证据的回复。
## Requirements
### Requirement: 对话语义触发 fast-search 与 site-search
无显式 slash command 时，主 agent SHALL 按对话语义自动派发：通用查询语气派 fast-search；定向官方站语气或命中权威性敏感主题（临床 / 专利 / 学术等）派 site-search。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-21

#### Scenario: 通用关键词触发 fast-search
- **WHEN** 用户说「查一下当前最流行的开源 LLM 推理框架」
- **THEN** 主 agent 派出 fast-search subagent，不要求用户跑任何 slash command

#### Scenario: 点名官方站触发 site-search
- **WHEN** 用户说「去 react.dev 查 Suspense 的最新用法」
- **THEN** 主 agent 派出 site-search subagent，目标站为 react.dev

### Requirement: 派发前必须用 TaskCreate 注册任务
主 agent MUST 在调 Task 工具派出任何 subagent 之前调用 `TaskCreate` 注册任务。任务描述 MUST 面向用户，不写 AI 内部叙事。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-21

#### Scenario: 派 deep-search 前先 TaskCreate
- **WHEN** 主 agent 准备派出 deep-search
- **THEN** TaskCreate 已先调用一次，注册的 task 描述对用户可读

#### Scenario: 同 turn 派多个 subagent
- **WHEN** deep-search 一轮内派 3 个 fast-search
- **THEN** 这 3 个 Task 工具调用在同一 message 内一次性发起（并行），不是串行

### Requirement: 派 subagent 时启动协作邀请
主 agent 在派出第一个 subagent 时 SHALL 向用户输出**一行**简洁、非阻塞的提示，邀请用户在等候期间贴入额外的数据源或查询条件。该提示每次 run 至少出现一次。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-21

#### Scenario: deep-search 启动时显示邀请
- **WHEN** 主 agent 派出 deep-search subagent
- **THEN** 用户屏幕上有一行提示「💡 如果你已经知道权威数据源或希望使用的查询条件，可以直接贴进来，AI 会优先采用」

#### Scenario: 用户中途贴入数据源
- **WHEN** 用户在 deep-search 运行期间贴入一个 URL 列表
- **THEN** 主 agent 把它视为高优先级 hint，注入到下一轮派发的 subagent prompt 中

### Requirement: 主 agent 最终回复必须挂证据
主 agent 在向用户回复任何来自搜索的判断、用语、概念、代码实现、数字时 MUST 附带循证证据：原始 URL 必填；结论性强的内容含关键原文摘录；有数字则保留关键数字。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-21

#### Scenario: 给结论附 URL
- **WHEN** 主 agent 在回复中陈述「React 19 引入了 useTransition」
- **THEN** 该结论后跟随至少一个原始 URL 链接，便于用户跳到源头

#### Scenario: 关键数字保留
- **WHEN** 主 agent 在回复中提到「TGI 比 vLLM 快 X%」
- **THEN** 该数字旁附带原文摘录或来源 URL，不允许只给数字不给来源

### Requirement: 循证四步工作流（所有 subagent + 主 agent 都遵循）
整体调研逻辑 MUST 遵循严格循证四步：(1) 先在起点搜（路由表见 `~/.config/search-crew/routing.yaml`）；(2) 不足时扩展到通用搜索 / 其他来源；(3) 关键结论 MUST 派 site-search 回到官方路径复核；(4) 未通过复核的内容 MUST 在最终产物中显式标注「未在官方源验证」。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-21

#### Scenario: 命中临床主题必须先到 clinicaltrials.gov
- **WHEN** 用户查询涉及临床试验
- **THEN** 主 agent 不允许直接派 fast-search 做通用搜索；MUST 先派 site-search 到 clinicaltrials.gov 和 pubmed.ncbi.nlm.nih.gov

#### Scenario: 通用源得到关键结论后回官方复核
- **WHEN** fast-search 通过博客得到一个关键技术结论
- **THEN** 主 agent / deep-search 在使用该结论前 MUST 派一个 site-search 到对应官方文档站复核

#### Scenario: 官方源无记录则显式标注
- **WHEN** site-search 复核时官方源未找到对应记录
- **THEN** 该结论在最终回复中以「未在官方源验证」前缀呈现，不得伪装为已验证事实

### Requirement: API key 完全可选，未配置时 fallback 到内置工具
所有 backend API key MUST 是可选的。未配置时，搜索 / 抓取脚本 MUST 返回明确的 fallback marker（`WEBSEARCH_FALLBACK` / `WEBFETCH_FALLBACK`）；调用方 MUST 改用 Claude Code 内置 WebSearch / WebFetch。系统在零 key 状态下 SHALL 仍能完成基本调研。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-21

#### Scenario: 零 key 时搜索 fallback
- **WHEN** 环境变量 `JINA_API_KEY` 与 `SERPER_API_KEY` 均未设置，主 agent 派 fast-search
- **THEN** `search.py` stdout 输出 `"fallback": "WEBSEARCH_FALLBACK"`，fast-search 接管后改用 Claude Code 内置 WebSearch 完成本次任务

### Requirement: 主 agent 最终回复 cost 总览不超过一行
主 agent 在最终回复结尾 MUST 追加且仅追加**一行** cost 总览（形如 `📊 本次估算 ~$X.XXX USD（N 次调用）`）。回复 MUST NOT 出现 `/tmp/search-crew/` 路径字符串或详细 cost 拆分。用户追问明细时主 agent SHALL Read `<run_root>/usage-summary.md` 后呈现拆分。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-21

#### Scenario: 一次完整调研结束
- **WHEN** 主 agent 完成调研并给用户最终回复
- **THEN** 回复结尾有且仅有一行 cost 总览；回复正文不含 `/tmp/search-crew/` 字符串、不复述按 backend / subagent 的拆分

#### Scenario: 用户追问明细
- **WHEN** 用户在 cost 总览出现后说「按 backend 拆开看」
- **THEN** 主 agent 用 Read 读取 `<run_root>/usage-summary.md` 后呈现拆分；run_root 路径由 subagent 派发时记下，不靠主 agent 自己回想字符串

### Requirement: ROUTING 起点表新增 AI 综述层
`~/.config/search-crew/routing.yaml`（与 plugin `defaults/routing.yaml`）MUST 新增 `ai_summary:` 顶层段，描述「query 未命中任何硬规则时，优先派 AI 综述 backend 作为第一跳」的策略。该段 MUST 含：`enabled`（默认 true）、`selection_order`（默认 `[grok, doubao, gemini]`）、`fallback_on_no_key`（默认 `jina`）、`models`（每个 backend 的 `fast` / `deep` 档 model id）。AI backend 用品牌名 `grok` / `gemini` / `doubao`；API key 走 env（`GROK_API_KEY` / `GEMINI_API_KEY` / `DOUBAO_API_KEY`），model 选择只走 `ai_summary.models`，MUST NOT 在代码 hardcode 或用 env 配 model。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-26

#### Scenario: defaults/routing.yaml 含 ai_summary 段
- **WHEN** 读取 `defaults/routing.yaml`
- **THEN** 文件顶层存在 `ai_summary:` 段，含 `enabled`、`selection_order`、`fallback_on_no_key`、`models` 四个键；`models.<backend>` 下含 `fast` / `deep` 两档 model id

#### Scenario: 硬规则优先级高于 AI 综述
- **WHEN** query 命中临床研究 / 专利 / 官方文档等硬规则
- **THEN** ROUTING 起点表的 AI 综述层 MUST 被跳过，按硬规则派 site-search

#### Scenario: 用户禁用 AI 综述层
- **WHEN** 用户改 `~/.config/search-crew/routing.yaml` 中 `ai_summary.enabled: false`
- **THEN** 所有 subagent 都不调用 AI backend，回到原有 jina/serper 路径

### Requirement: 主 agent cost 总览一行扩展为「带覆盖面数字」格式
主 agent 在最终回复结尾的那一行 cost 总览 SHALL 扩展格式为 `📊 本次估算 ~$X.XXX USD（N 次调用 · M 个源 · K 次触发站点调用上限）`。其中 `M 个源` 为本次 run 实际调用过的 distinct backend / site 数，`K 次触发站点调用上限` 为被上限拦下的请求数（K=0 时该段省略）。该行 MUST 仍保持单行，MUST NOT 拆分成多行，MUST NOT 出现 `/tmp/search-crew/` 路径字符串。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-26

#### Scenario: 正常一次调研
- **WHEN** 主 agent 完成调研，本次 run 调用 12 次、4 个不同源、未触发上限
- **THEN** 回复末尾仅有一行：`📊 本次估算 ~$0.043 USD（12 次调用 · 4 个源）`

#### Scenario: 触发站点调用上限
- **WHEN** 本次 run 内有 2 次请求被站点调用上限拦下
- **THEN** 回复末尾的 cost 行含 `· 2 次触发站点调用上限`

#### Scenario: 未变成多行
- **WHEN** 主 agent 输出最终回复
- **THEN** cost 总览整体仍是一行字符串，不含换行符

### Requirement: 唯一显式搜索 slash command 是 /search-deep
系统 SHALL 仅提供一个用户显式触发的搜索 slash command：`/search-deep <主题>`（插件命名空间下为 `/search-crew:search-deep`），用于强制启动 deep-search 流。其余搜索场景 MUST 由对话语义自动判断派发。命令的短名 MUST 用 `search-*` 前缀，避免占用 `/deep-search`、`/setup` 这类通用全局名。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-26

#### Scenario: 用户输入 /search-deep 跟主题
- **WHEN** 用户输入 `/search-deep 调研开源 LLM 推理框架`
- **THEN** 主 agent 派出 deep-search subagent 处理该主题（subagent 名仍为 deep-search，未改）

#### Scenario: 不存在通用 /search 或裸 /deep-search
- **WHEN** 用户尝试 `/search ...`
- **THEN** Claude Code 报告该命令不存在；真正的命令是 `/search-deep`（或 `/search-crew:search-deep`）

### Requirement: 主 agent 读 URL 优先用 web-page-fetch skill
主 agent 在需要读取具体 URL 的页面 / 文件内容时 SHALL 优先经 `web-page-fetch` skill 调 `fetch.py`，而非直接用内置 WebFetch；仅在 `fetch.py` 返回 `WEBFETCH_FALLBACK` 时回落内置 WebFetch，返回 `anti_bot` 时诚实失败。此偏好为软引导（Claude Code 无法物理禁用内置 WebFetch），靠 skill description + 本 requirement 落实。

#### Scenario: 主 agent 读 URL
- **WHEN** 用户给出一个 URL 要求读取内容
- **THEN** 主 agent 优先调 `fetch.py`（web-page-fetch skill 指引），按其三态结果处理


## MODIFIED Requirements

### Requirement: 显式搜索 slash command：/search-deep、/search-wide、/search-fast
系统 SHALL 提供三个用户显式触发的搜索 slash command：`/search-deep <主题>`（强制 deep-search 深度循环）、`/search-wide <批量对比需求>`（强制 wide-search 对照矩阵）、`/search-fast <主题>`（**主 agent 直连 `ai_search.py` 出 AI 综述快答，不派 subagent**）。插件命名空间下分别为 `/search-crew:search-deep`、`/search-crew:search-wide`、`/search-crew:search-fast`。命令短名 MUST 用 `search-*` 前缀，避免占用 `/deep-search`、`/setup` 这类通用全局名。无显式命令时其余搜索场景 MUST 仍由对话语义自动判断派发。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-28

#### Scenario: 用户输入 /search-wide 跟批量对比需求
- **WHEN** 用户输入 `/search-wide 对比这 12 个开源推理框架的性能/许可证/活跃度`
- **THEN** 主 agent 派出 wide-search lead 处理该批量对照需求

#### Scenario: 用户输入 /search-fast 跟主题
- **WHEN** 用户输入 `/search-fast 当前最流行的开源向量数据库`
- **THEN** 主 agent **直接跑 `ai_search.py`** 拿 AI 综述 + citations 呈现，全程不派 subagent

#### Scenario: /search-deep 行为不变
- **WHEN** 用户输入 `/search-deep 调研开源 LLM 推理框架`
- **THEN** 主 agent 派出 deep-search subagent 处理该主题

#### Scenario: 不存在裸通用 /search
- **WHEN** 用户尝试 `/search ...`
- **THEN** Claude Code 报告该命令不存在；真正的命令是 `/search-deep`、`/search-wide`、`/search-fast`（或带 `/search-crew:` 命名空间）

### Requirement: 派 search subagent 前造 run 目录并经环境变量下传
主 agent 在派出 search subagent（site/deep/wide，及内部 worker evidence-search）**之前** MUST 用 `run_paths.py --new` 造一个唯一 run 目录，并在派发时通过 `SEARCH_CREW_RUN_ROOT` 环境变量把**目录路径**传给该 subagent。被派的 subagent MUST 在其所有脚本调用前带上该变量、产物写该目录下；lead（deep/wide）再派下级 worker 时 MUST 把同一 `SEARCH_CREW_RUN_ROOT` 原样传下去，使整条派发链的产物 / cost 全落同一目录。`/search-fast` 虽不派 subagent，主 agent 跑 `ai_search.py` 时 SHALL 同样先造 run 目录并经该变量传入，使快答的打点也落独立目录。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-28

#### Scenario: 主 agent 直连快答也用 run 目录
- **WHEN** 用户触发 `/search-fast <主题>`
- **THEN** 主 agent 先 `run_paths.py --new` 造目录，再带 `SEARCH_CREW_RUN_ROOT=<目录>` 跑 `ai_search.py`，打点落该目录

#### Scenario: lead 向 worker 传递 run 目录
- **WHEN** deep-search 收到 `SEARCH_CREW_RUN_ROOT` 后派 evidence-search worker
- **THEN** worker 的 Task 派发带同一 `SEARCH_CREW_RUN_ROOT`，worker 产物与打点落 lead 的同一目录

### Requirement: 主 agent 路由「批量对比/分析 N 个同类对象」到 wide-search
主 agent 在无显式命令时，若对话语义识别为「对 N 个**同类对象**跑**同一套分析维度**、要对照结果」（如「对比这 15 个框架的 X/Y/Z」「调研这 20 家供应商的价格/SLA」），SHALL 自动派 wide-search。单对象多角度深挖仍走 deep-search；只想要一口现成答案走 `/search-fast`（AI 综述快答）；需要结构化证据的单轮通用调研走 evidence-search（或由 deep/wide 内部派）。

#### Scenario: 语义识别批量对照需求
- **WHEN** 用户说「帮我对比这 10 个 Rust HTTP 框架的吞吐、生态、上手难度」（未用 slash 命令）
- **THEN** 主 agent 自动派 wide-search lead，而非把 10 个对象塞进一个 worker

#### Scenario: 单对象深挖不误派 wide-search
- **WHEN** 用户说「深入研究 vLLM 的调度器实现」（单对象）
- **THEN** 主 agent 派 deep-search，不派 wide-search

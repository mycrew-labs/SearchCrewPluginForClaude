# wide-search Specification

## Purpose
TBD - created by archiving change wide-search. Update Purpose after archive.
## Requirements
### Requirement: wide-search 拆「对象清单 + 统一分析 schema」并派发前确认
wide-search lead 收到批量对比需求时，MUST 先拆出两样东西：①**对象清单**（要分析哪些同类对象）②**统一分析 schema**（矩阵的列 / 分析维度）。在派发任何 worker **之前**，lead MUST 把对象清单与列 schema 输出给用户确认一次（因为列错一次会导致 N 个 worker 全跑偏，损失 ×N）。用户一句话放行（或修正）后再派发；用户未回应时 MUST NOT 擅自铺开 N 个 worker。

#### Scenario: 派发前确认 schema
- **WHEN** lead 从「对比这 12 个推理框架的性能/许可证/活跃度」拆出对象清单 + 列
- **THEN** lead 先把「12 个对象 + 性能/许可证/活跃度 三列」输出给用户确认，确认后才派 worker

### Requirement: wide-search 受 max_items 硬上限约束
wide-search MUST 读取 `~/.config/search-crew/limits.yaml` 的 `wide_search.max_items`（默认 12）。对象数超过该上限时，lead MUST 分批处理（跑完一批再跑下一批）或要求用户收窄范围，MUST NOT 一次性铺超过 max_items 个并行 worker。

#### Scenario: 超上限分批
- **WHEN** 用户要求对比 30 个对象，max_items=12
- **THEN** lead 分批（如 12 + 12 + 6）或请用户收窄，不一次性派 30 个 worker

### Requirement: wide-search 产出可回溯证据的对照矩阵（双格式）
wide-search MUST 产出与 deep-search 语义等价的双格式产物：`report.md`（markdown 表格，行=对象、列=schema 维度，每格附证据 anchor 指向 `traces/`）+ `report.html`（可按列排序的表格，与 report.md 语义等价）。每个 worker 的原始产物 MUST 保留在 `traces/<worker>-<sid>/`，使矩阵每格可回溯到源 URL。cost 一行与 usage-summary 由 `finalize_usage.py` 接管（沿用 deep-search 约定）。

#### Scenario: 矩阵每格可回溯
- **WHEN** 矩阵某格写「vLLM 吞吐 24k tok/s」
- **THEN** 该格附 anchor 指向对应 worker trace 中的源 URL / 原文

#### Scenario: 双格式语义等价
- **WHEN** report.md 标了某对象某维度「未获取」
- **THEN** report.html 同样呈现该「未获取」，不得多填或少填

### Requirement: wide-search 单点 worker 失败不毁整张矩阵
某对象的 worker 失败 / 未查到数据时，lead MUST 在矩阵对应行 / 格标注「未获取」并照常产出整张矩阵，MUST NOT 因单点失败放弃全部结果。

#### Scenario: 部分对象查不到
- **WHEN** 12 个 worker 中有 2 个失败
- **THEN** 矩阵照常产出，那 2 行对应格标「未获取」，其余 10 行正常

### Requirement: wide-search plan/synth 两模式；worker-spawn 由主 agent 负责
Claude Code harness 不允许 subagent 内 Task，worker-spawn MUST 由主 agent（command）在 plan 阶段结束后负责。wide-search plan 模式 MUST 从 topic 中拆出对象清单 + 分析 schema，与用户确认后输出紧凑 JSON `{"objects":[...],"columns":[...]}` 返回主 agent；主 agent MUST 同 turn 并发 Task(evidence-search×N)，每个 worker 接收 (object, schema_columns, target_dir)；wide-search synth 模式 MUST 只接收 run_root，自发现 traces/，读 evidence-summary.md 矩阵行段，汇成矩阵报告，返回两个路径字符串。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-29

#### Scenario: plan 模式输出 schema JSON
- **WHEN** Task(wide-search, mode=plan, topic=...) 被调用
- **THEN** 与用户确认后输出 `{"objects":[...],"columns":[...]}` JSON；返回前 MUST 得到用户确认（×N 风险）

#### Scenario: synth 模式自发现 traces 建矩阵
- **WHEN** Task(wide-search, mode=synth, run_root=..., schema=...) 被调用
- **THEN** ls <run_root>/wide-search/traces/，每个子目录对应一个对象；读 evidence-summary.md 矩阵行段；产出 report.md 表格 + report.html 可排序矩阵；返回两个路径字符串


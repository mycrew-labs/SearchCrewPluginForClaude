## REMOVED Requirements

### Requirement: wide-search 一对象一 worker、同 turn 并行、复用 evidence/site-search
**Reason**: worker-spawn 移到主 agent（harness 不允许 subagent 嵌套 Task）；wide-search 拆成 plan + synth 两模式。由下方新需求取代。
**Migration**: worker 由主 agent 并发 spawn，wide-search plan 模式出 schema JSON，synth 模式自发现 traces/ 汇矩阵。

## ADDED Requirements

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

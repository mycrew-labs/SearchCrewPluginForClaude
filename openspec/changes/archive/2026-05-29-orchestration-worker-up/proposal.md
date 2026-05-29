## Why

实测发现：Claude Code 的 harness **不允许 subagent 再派 subagent**（Task 工具在 subagent 内不可用）。这推翻了 deep/wide lead 内部 Task(evidence-search) 的架构假设——实际上 deep-search 在测试中被迫自己跑脚本，无法真正 spawn 并行 worker。

直接把 worker-spawn 移到主 agent 层（"往上移一层"）可以解决 Task 约束，但会导致 **context 爆炸**：主 agent 要读所有 worker 返回内容才能传给 synthesizer。

**本 change 的核心洞察**：主 agent 只需传**一个目录路径**，synthesizer 自己发现 traces/。协议极小：

- 主 agent → planner：传 topic，收 紧凑 JSON plan（~400 token）
- 主 agent → N×evidence-search：传 (query, target_dir)，收 (path, 一句话)（~20 token/个）
- 主 agent → synthesizer：传 run_root（**一个字符串**），收 (html_path, md_path)（两个字符串）

**整个调研主 agent 净增 context = 几百 token，与 N 无关**。

## What Changes

- **deep/wide 拆成两个调用阶段**（plan mode + synth mode）：不新建 agent 文件，同一 agent 通过 `mode=plan|synth` 参数区分行为。
  - plan 模式：输出紧凑 JSON plan（子任务列表 / schema+对象），写 plan.md，返回 plan JSON 字符串
  - synth 模式：只接收 `run_root`，自己 ls traces/ 发现 worker 产物，综合产出 report.md + report.html，返回两个路径
- **worker-spawn 移到主 agent（commands）**：`/search-deep` 和 `/search-wide` 命令在两次 Task 调用之间负责并发 spawn evidence-search workers。
- **evidence-search 协议简化**：接收 `(query, target_dir)` 或 wide 场景的 `(object, schema_columns, target_dir)`，返回仅 `(target_dir, one-line-summary)`。
- **traces 发现协议**：synthesizer 通过 `ls <run_root>/deep-search/traces/`（或 wide-search/traces/）发现所有 worker 输出，先读各 INDEX.md，按需深入——无需主 agent 传文件名列表。

## Capabilities

### Modified Capabilities

- `orchestration`：MODIFY 「worker-spawn 在主 agent 层做（commands），不在 lead subagent 内做」；传递协议改为最小路径传递。
- `deep-search`：MODIFY 「拆成 plan + synth 两个 mode，synth 接收 run_root 自发现 traces」。
- `wide-search`：MODIFY 「同上；schema 确认仍在 plan mode；worker-spawn 移到主 agent」。
- `evidence-search`：MODIFY 「协议简化，返回 (target_dir, summary) 两个字段」。

## Impact

- 修复 subagent 嵌套约束，worker 真正并行（主 agent 同 turn 并发 Task）
- 主 agent context 与采集内容量解耦
- deep/wide 保留独立 subagent 身份（context 隔离）
- locked 影响：deep-search「派活优先」、wide-search「一对象一 worker」、orchestration「造 run 目录」均需 MODIFY

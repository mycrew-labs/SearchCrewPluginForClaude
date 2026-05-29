## ADDED Requirements

### Requirement: 主 agent 直接 spawn evidence-search workers；lead 只做规划与综合
Claude Code harness 不允许 subagent 内嵌套 Task 调用，因此 worker-spawn MUST 在主 agent（command 层）完成。deep-search / wide-search 作为 subagent 仅负责「plan（规划）」和「synth（综合）」两个阶段；主 agent 在两次 Task 调用之间负责并发 spawn evidence-search workers。传递协议 MUST 保持最小：plan 阶段返回紧凑 JSON（~300-500 token），synthesizer 只接收 run_root（一个路径字符串），通过 `ls traces/` 自发现 worker 产物——主 agent context 增量与采集量无关。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-29

#### Scenario: /search-deep 两阶段流程
- **WHEN** 用户触发 `/search-deep <topic>`
- **THEN** 主 agent 先 Task(deep-search mode=plan) 得紧凑 plan JSON，再并发 Task(evidence-search×N)，再 Task(deep-search mode=synth run_root) 得报告路径；主 agent context 只增加 JSON plan + N×(path,summary) + 两个路径字符串

#### Scenario: synthesizer 只接收路径不接收内容
- **WHEN** 主 agent 调用 synthesizer（deep/wide mode=synth）
- **THEN** 只传 run_root 一个路径；synthesizer 自己 ls traces/ 发现 worker 产物，不由主 agent 传文件名列表

## MODIFIED Requirements

### Requirement: 派 search subagent 前造 run 目录并经环境变量下传
主 agent 在派出 search subagent（site/evidence/deep/wide）**之前** MUST 用 `run_paths.py --new` 造一个唯一 run 目录，并在派发时通过 `SEARCH_CREW_RUN_ROOT` 环境变量把目录路径传给该 subagent。被派的 subagent MUST 在其所有脚本调用前带上该变量、产物写该目录下；evidence-search workers MUST 各写到 `<run_root>/deep-search/traces/<task_id>/`（deep）或 `<run_root>/wide-search/traces/<obj_id>/`（wide）子目录。本需求仅约束派 subagent 的场景；`/search-fast` 直连不造目录。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-29

#### Scenario: 主 agent 并发 spawn workers
- **WHEN** 主 agent 按 plan 派 N 个 evidence-search workers
- **THEN** 同 turn 一次性发起 N 个 Task，每个带同一 SEARCH_CREW_RUN_ROOT；各 worker 产物落 traces/<id>/ 子目录

#### Scenario: synthesizer 只收 run_root
- **WHEN** 主 agent 调用 Task(deep-search mode=synth)
- **THEN** 传 run_root；不传文件名列表；synthesizer 通过 ls traces/ 自发现

## 1. agents/evidence-search.md

- [x] 1.1 加「每次调用产出 evidence-summary.md（≤60 行）」工作流步骤
- [x] 1.2 明确返回格式两行：`summary_path: <path>` + `summary: <一句话>`
- [x] 1.3 wide 场景：接收 object + schema_columns，summary 额外含矩阵行段
- [x] 1.4 删除「返回 (target_dir, 一句话摘要, run_root) 三元组」旧约定

## 2. agents/deep-search.md

- [x] 2.1 加「## 规划模式（mode=plan）」段：输出 tasks JSON + 写 plan.md，不 spawn worker
- [x] 2.2 加「## 综合模式（mode=synth）」段：接收 run_root，ls traces/，读各 evidence-summary.md，按需进 traces/，产 report.md + report.html，返回两个路径字符串
- [x] 2.3 明确 synth 模式 MUST NOT 尝试 Task（harness 约束）；plan 模式亦不 spawn worker
- [x] 2.4 删除「第一轮规划 + 同 turn 并行派发 worker」旧流程

## 3. agents/wide-search.md

- [x] 3.1 加 plan 模式：拆对象+schema，与用户确认，输出 schema JSON，不 spawn worker
- [x] 3.2 加 synth 模式：接收 run_root + schema，ls traces/，读 evidence-summary.md，建矩阵，返回两个路径
- [x] 3.3 删除旧「同 turn 并行派发 worker」段

## 4. commands/search-deep.md

- [x] 4.1 重写为两阶段流程：Task(plan) → 并发 Task(evidence-search×N) → Task(synth)
- [x] 4.2 plan 阶段：主 agent 读 JSON plan，按 tasks 构造 evidence-search 调用（query_en + query_zh → 双语双 worker 或单 worker 带双语）
- [x] 4.3 worker 收到：(query, target_dir=<run_root>/deep-search/traces/<id>/)；返回：(summary_path, summary)
- [x] 4.4 synth 阶段：只传 run_root，收两个路径

## 5. commands/search-wide.md

- [x] 5.1 重写为两阶段：Task(plan+confirm) → 并发 Task(evidence-search×N) → Task(synth)
- [x] 5.2 plan 阶段返回 schema JSON，主 agent 按对象构造 worker 调用
- [x] 5.3 worker 收到：(object, schema_columns, target_dir=<run_root>/wide-search/traces/<obj_id>/)
- [x] 5.4 synth 阶段：传 run_root + schema JSON

## 6. 归档前：锁确认 gate

- [x] 6.1 `openspec validate orchestration-worker-up --strict` 通过
- [x] 6.2 完工简报：MODIFY orchestration「主 agent spawn workers」+ deep「plan+synth mode」+ wide「plan+synth mode」+ evidence「summary 文件」共 4 条 locked；逐条确认
- [ ] 6.3 用户确认 → bump version → archive → commit → push
- [ ] 6.4 **manual** 实测：/search-deep 两阶段跑通，traces/ 含 evidence-summary.md，report.md + report.html 产出；/search-wide 同验

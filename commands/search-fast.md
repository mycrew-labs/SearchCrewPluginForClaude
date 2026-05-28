---
name: search-fast
description: 显式发起一次通用快速调研。主 agent 派一个 fast-search subagent，搜一轮、抓一批、整理摘要即返回，不循环。
---

## 用户主题

`{{args}}`

## 主 agent 工作流

`/search-fast` 是 fast-search 的显式入口——把原本只能靠对话语义自动触发的 fast-search 暴露成命令。语义自动触发的老路径保留不变（用户不打命令、只是用通用查询语气时，主 agent 仍会自动派 fast-search）。

### 1. TaskCreate 建任务清单

派之前调 `TaskCreate`，描述面向用户：「快速调研：{{args}}」。

### 2. 派 fast-search

用 Task 工具派 `fast-search`，参数：

- `query`：原样传 `{{args}}`
- `hint`：如能从用户措辞推断方向 / 来源偏好，加这一段
- `target_dir` 不传，让 fast-search 自己用 session-id 决定

fast-search 是单轮 worker，只回 `(target_dir, 一句话摘要, run_root)`。

### 3. 阅读产物

Read `<target_dir>/INDEX.md`，按需跳进具体 `fast-search-NNN.md`。

### 4. TaskUpdate 标 completed

### 5. 最终回复用户

- **核心结论**：用你自己的话综合，**必须**附证据 URL / 关键原文 / 关键数字，不编造
- **cost 一行**：调 `python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/finalize_usage.py <run_root> --subagent fast-search --one-line` 拿现成字符串拼到末尾。**MUST 带 `--subagent fast-search`**——run_root 是会话级共享目录，不切片会把整会话的累计调用都算进来（显示成上百次调用 / 一堆"触发上限"，吓人且不准）；切片后只显示本次 fast-search 的真实开销

**不要**写出 `<run_root>` 路径或展开 cost 拆分。

## 何时该升级

如果一轮 fast-search 不够（需要多轮挖掘 / 循证回查）→ 建议用户改用 `/search-deep`；如果是「对 N 个同类对象跑同一套分析」→ 建议 `/search-wide`。

## 关键约束

- TaskCreate 必须在派发之前
- 单轮即返回，不在本命令里循环加派
- cost 总览只一行

---
name: search-deep
description: 启动一次深度调研。主 agent 两阶段编排：先 Task(deep-search mode=plan) 获取子任务 JSON，再并发 Task(evidence-search×N)，最后 Task(deep-search mode=synth) 综合产出报告。
---

## 用户主题

`{{args}}`

## 主 agent 工作流

### 1. TaskCreate + 协作邀请

```
TaskCreate：深度调研：{{args}}
```

> 💡 如果你已经知道权威数据源或希望使用的查询条件，可以直接贴进来，AI 会优先采用。

### 2. 派发前澄清（明显歧义先一句话，非阻塞）

topic 有明显歧义 / 范围过宽时，先一句话含默认方向；已清晰则直接派。

### 3. 造本次 run 目录

```bash
python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/run_paths.py --new
```

记下输出路径作 `<run_root>`。

### 4. 阶段一：规划（plan）

```
Task(deep-search, mode=plan, topic={{args}}, run_root=<run_root>)
```

deep-search 返回**紧凑 JSON**（stdout，直接 parse，无需 Read 文件）：

```json
{
  "complexity": "medium",
  "tasks": [
    {"id": "T1", "title": "...", "query_en": "...", "query_zh": "..."},
    {"id": "T2", "title": "...", "query_en": "...", "query_zh": "..."}
  ]
}
```

### 5. 阶段二：并发采集（同 turn 发起所有 Task，勿串行）

按 plan JSON 的 tasks，**同一 message 内**并发 Task(evidence-search × N)。

每个 worker 的 Task prompt 包含：
- `query`：task 的 query_en 和 query_zh（双语）
- `target_dir`：`<run_root>/deep-search/traces/<task.id>/`（完整绝对路径）
- `SEARCH_CREW_RUN_ROOT=<target_dir>`（worker 用它定位脚本路径）

每个 worker 返回两行：
```
summary_path: <target_dir>/evidence-summary.md
summary: <一句话>
```

主 agent 收到 N×(summary_path, summary)——**只存这两个字符串，不读文件内容**。

### 6. 阶段三：综合（synth）

```
Task(deep-search, mode=synth, run_root=<run_root>)
```

只传 `run_root` 一个字符串。deep-search 自己 ls traces/ 发现所有 worker 产物，读 evidence-summary.md，综合出 report.md + report.html。

返回三行：
```
<run_root>/deep-search/report.html
<run_root>/deep-search/report.md
📊 本次估算 ~$X.XXX USD（N 次调用 · M 个源）
```

### 7. TaskUpdate + 阅读报告

TaskUpdate 标 completed，Read `<run_root>/deep-search/report.md`。

### 8. 最终回复用户

**块 1：报告路径**
```
📄 调研报告（浏览器打开更直观）：
   open <run_root>/deep-search/report.html      # mac
```

**块 2：核心结论**（用自己的话，必须附证据 URL / 关键数字，不编造）

**块 3：cost 一行**（直接用 deep-search synth 返回的第三行）

**绝对不要**写出 `<run_root>` 路径、详细 cost 拆分。

## 关键约束

- TaskCreate 必须在派发之前
- 阶段二的 N 个 Task **MUST** 在同一 message 内并发发起（同 turn）
- 只传路径，不传文件内容——主 agent context 与采集量解耦
- cost 总览只一行

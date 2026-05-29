---
name: search-wide
description: 启动一次广度调研。主 agent 两阶段编排：先 Task(wide-search mode=plan) 确认 schema，再并发 Task(evidence-search×N)，最后 Task(wide-search mode=synth) 汇成对照矩阵。
---

## 用户主题

`{{args}}`

## 主 agent 工作流

### 1. TaskCreate + 协作邀请

```
TaskCreate：广度调研（对照矩阵）：{{args}}
```

> 💡 如果你已经明确要对比哪些对象、按哪几个维度，可以直接列出来，AI 会优先采用。

### 2. 造本次 run 目录

```bash
python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/run_paths.py --new
```

记下输出路径作 `<run_root>`。

### 3. 阶段一：规划 + 用户确认 schema（plan）

```
Task(wide-search, mode=plan, topic={{args}}, run_root=<run_root>)
```

wide-search 先与用户确认对象清单 + 列 schema（×N 风险，必须等用户放行），再返回紧凑 JSON：

```json
{
  "objects": ["Milvus", "Qdrant", "Weaviate"],
  "columns": ["性能", "许可证", "部署难度", "适用规模"]
}
```

**注意**：wide-search 在 plan 模式里会与用户交互确认 schema，你等它返回 JSON 再继续。

### 4. 阶段二：并发采集（同 turn 发起所有 Task）

按 JSON 的 objects，**同一 message 内**并发 Task(evidence-search × N，N ≤ max_items)。

每个 worker 的 Task prompt 包含：
- `object`：研究的具体对象（如 "Milvus"）
- `schema_columns`：columns JSON 数组（如 `["性能", "许可证", "部署难度", "适用规模"]`）
- `target_dir`：`<run_root>/wide-search/traces/obj_<object>/`（完整绝对路径）
- `SEARCH_CREW_RUN_ROOT=<target_dir>`

每个 worker 返回两行：
```
summary_path: <target_dir>/evidence-summary.md
summary: <一句话>
```

**主 agent 只存这两个字符串，不读文件内容**。

超过 max_items 时分批（跑完一批再下一批），不一次铺满。

### 5. 阶段三：综合矩阵（synth）

```
Task(wide-search, mode=synth, run_root=<run_root>, schema=<JSON 字符串>)
```

只传 run_root + schema JSON 字符串。wide-search 自己 ls traces/，读各 evidence-summary.md 的矩阵行段，汇成对照矩阵报告。

返回三行：
```
<run_root>/wide-search/report.html
<run_root>/wide-search/report.md
📊 本次估算 ~$X.XXX USD（N 次调用 · M 个源）
```

### 6. TaskUpdate + 最终回复用户

**块 1：矩阵报告路径**（HTML 优先，可排序对比）
```
📄 对照矩阵（浏览器打开可按列排序）：
   open <run_root>/wide-search/report.html      # mac
```

**块 2：矩阵速读**（点出关键对照结论，附证据；「未获取」格如实说明）

**块 3：cost 一行**（synth 返回的第三行）

**绝对不要**写出 `<run_root>` 路径、详细 cost 拆分。

## 关键约束

- wide-search plan 模式**必须等用户确认 schema** 再进阶段二
- 阶段二的 N 个 Task **MUST** 同一 message 内并发（同 turn）
- 只传路径和 schema JSON，不传文件内容
- cost 总览只一行

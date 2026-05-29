## Context

Claude Code harness 约束：subagent 内 Task 工具不可用，无法嵌套派发。
现有架构假设 deep/wide lead 内部 Task(evidence-search)——已被实测推翻。

## Goals / Non-Goals

**Goals:**
- worker-spawn 移到主 agent，真正并行
- 主 agent context 与采集量解耦（只传路径，不传内容）
- deep/wide 保留独立 subagent（context 隔离）
- 协议尽可能小（synthesizer 只需 run_root 一个字符串）

**Non-Goals:**
- 不改 evidence-search 内部采集逻辑（双语并发、serper+bocha 等保留）
- 不改 ai_search / /search-fast

## Decisions

### D1：plan / synth 两阶段，同一 agent 文件用 mode 区分

`Task(deep-search, mode=plan, topic=...)` → `Task(deep-search, mode=synth, run_root=...)`

不拆文件，prompt 顶部声明行为。减少 agent 文件数，语义内聚。

### D2：plan 阶段输出紧凑 JSON 给主 agent

deep-search plan 阶段输出（stdout 返回主 agent）：

```json
{
  "tasks": [
    {"id": "T1", "title": "...", "query_en": "...", "query_zh": "..."},
    {"id": "T2", "title": "...", "query_en": "...", "query_zh": "..."}
  ]
}
```

wide-search plan 阶段输出：

```json
{
  "objects": ["Milvus", "Qdrant", "Weaviate"],
  "columns": ["性能", "许可证", "部署难度"]
}
```

主 agent context 增量：~300-500 token。plan.md 另写入磁盘供参考，但主 agent 通过 JSON 直接拿到结构化数据，无需 Read。

### D3：evidence-search 最小协议

输入（Task prompt 里传）：
- `query` 或 `query_en`/`query_zh`（由调用方决定单双语）
- `target_dir`：完整绝对路径（如 `/tmp/.../traces/T1/`）
- wide 场景加：`object`、`schema_columns`（JSON 数组）

返回（两行，主 agent 读）：
```
target_dir: /tmp/.../traces/T1/
summary: 一句话摘要
```

主 agent context 增量：每个 worker ~20 token。

### D4：synthesizer 只接收 run_root

```
Task(deep-search, mode=synth, run_root=/tmp/.../20260529T003811-2fa0fa)
```

synthesizer 内部：
1. `ls <run_root>/deep-search/traces/` → 发现所有子目录
2. 并发 Read 各子目录的 INDEX.md（紧凑）
3. 按需 grep/Read 具体证据文件
4. 写 report.md + report.html
5. 返回两个路径字符串

主 agent context 增量：最后收到两个字符串。

### D5：/search-deep 命令新流程

```
1. run_paths.py --new → run_root
2. Task(deep-search, mode=plan, topic, run_root) → plan JSON
3. 按 plan 同 turn 并发 Task(evidence-search×N)，各传 (query_en/zh, target_dir)
4. 收到 N×(target_dir, summary)——仅存字符串
5. Task(deep-search, mode=synth, run_root) → (html_path, md_path)
6. 呈现给用户
```

### D6：/search-wide 命令新流程

```
1. run_paths.py --new → run_root
2. Task(wide-search, mode=plan, topic, run_root) → {objects, columns} JSON + 用户确认
3. 同 turn 并发 Task(evidence-search×N)，各传 (object, schema_columns, target_dir)
4. 收到 N×(target_dir, summary)
5. Task(wide-search, mode=synth, run_root, schema) → (html_path, md_path)
6. 呈现给用户
```

## Risks / Trade-offs

- plan 阶段返回 JSON 要求 agent 输出格式稳定（加明确 format 指令）
- synthesizer 自发现 traces/ 要求目录结构一致（已有约定，worker 按 target_dir 写）
- wide-search plan + 用户确认在同一 subagent 内发生——仍可以，plan mode 可与用户交互

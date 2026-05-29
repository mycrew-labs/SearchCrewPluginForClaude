## ADDED Requirements

### Requirement: evidence-search 每次调用产出 evidence-summary.md 并返回其路径
每次 evidence-search 调用 MUST 在其 target_dir 下产出一个 `evidence-summary.md`（精炼，≤60 行）：含子任务描述、核心发现（按 ranking）、来源表（序号/ranking/url）、分歧标注、证据目录引用。返回值 MUST 是两行：`summary_path: <绝对路径>` 和 `summary: <一句话>`。主 agent 只存这两个字符串（context 极小）；synthesizer 读 summary 文件快速把握全貌，按需再进 traces/ 取原文引用。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-29

#### Scenario: 返回 summary 路径而非目录
- **WHEN** evidence-search 完成一次调用
- **THEN** 最后两行输出形如：
  ```
  summary_path: /tmp/.../traces/T1/evidence-summary.md
  summary: 找到 Qdrant/Milvus/Weaviate 官方 benchmark 数据，Qdrant p50 4ms 领先
  ```

#### Scenario: summary 文件内容精炼
- **WHEN** synthesizer 读 evidence-summary.md
- **THEN** 能在 ≤60 行内获取：子任务、核心发现（含 ranking）、来源表、分歧标注、证据目录路径；无需再读 traces/ 就能做初步综合

#### Scenario: wide 场景输出 schema 行填充
- **WHEN** evidence-search 收到 (object, schema_columns, target_dir)
- **THEN** summary 文件额外含按 schema_columns 填充的「矩阵行」段，每列一格附源 URL，供 wide-search synth 直接读取

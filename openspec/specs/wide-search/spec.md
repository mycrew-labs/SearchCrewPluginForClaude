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

### Requirement: wide-search 一对象一 worker、同 turn 并行、复用 evidence/site-search
wide-search lead MUST 为每个对象派一个独立 context 的 worker（避免单 context 串行处理 N 项导致的深度退化），且 MUST 在同一 message 内并行发起这些 Task 调用。worker MUST 复用现有 evidence-search（默认，haiku 廉价档）或 site-search（个别对象需官方源精确查时），MUST NOT 新建 worker subagent，MUST NOT 自己拼 backend 请求。派每个 worker 的 Task prompt MUST 含任务契约四要素（目标 / 输出格式 / 工具源指引 / 边界），其中「输出格式」MUST 要求 worker 按 schema 填一行、每格附源 URL。

#### Scenario: 每对象独立 worker 并行
- **WHEN** lead 确认了 12 个对象的 schema
- **THEN** lead 在同一 message 内并行派最多 max_items 个 worker，每个研究一个对象

#### Scenario: worker 复用 evidence-search
- **WHEN** 某对象只需通用网络调研
- **THEN** lead 派 evidence-search（haiku）而非新建 worker subagent


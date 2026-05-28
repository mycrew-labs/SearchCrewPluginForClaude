## REMOVED Requirements

### Requirement: wide-search 一对象一 worker、同 turn 并行、复用 fast/site-search
**Reason**: worker 从 fast-search 改名 evidence-search；由下方同义需求取代。
**Migration**: 行为不变，worker 派 evidence-search（原 fast-search）。

## ADDED Requirements

### Requirement: wide-search 一对象一 worker、同 turn 并行、复用 evidence/site-search
wide-search lead MUST 为每个对象派一个独立 context 的 worker（避免单 context 串行处理 N 项导致的深度退化），且 MUST 在同一 message 内并行发起这些 Task 调用。worker MUST 复用现有 evidence-search（默认，haiku 廉价档）或 site-search（个别对象需官方源精确查时），MUST NOT 新建 worker subagent，MUST NOT 自己拼 backend 请求。派每个 worker 的 Task prompt MUST 含任务契约四要素（目标 / 输出格式 / 工具源指引 / 边界），其中「输出格式」MUST 要求 worker 按 schema 填一行、每格附源 URL。

#### Scenario: 每对象独立 worker 并行
- **WHEN** lead 确认了 12 个对象的 schema
- **THEN** lead 在同一 message 内并行派最多 max_items 个 worker，每个研究一个对象

#### Scenario: worker 复用 evidence-search
- **WHEN** 某对象只需通用网络调研
- **THEN** lead 派 evidence-search（haiku）而非新建 worker subagent

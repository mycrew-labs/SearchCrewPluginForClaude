## MODIFIED Requirements

### Requirement: ROUTING 起点表新增 AI 综述层
`~/.config/search-crew/routing.yaml`（与 plugin `defaults/routing.yaml`）MUST 新增 `ai_summary:` 顶层段，描述「query 未命中任何硬规则时，优先派 AI 综述 backend 作为第一跳」的策略。该段 MUST 含：`enabled`（默认 true）、`selection_order`（默认 `[grok, doubao, gemini]`）、`fallback_on_no_key`（默认 `jina`）、`models`（每个 backend 的 `fast` / `deep` 档模型配置）。AI backend 用品牌名 `grok` / `gemini` / `doubao`；API key 走 env（`GROK_API_KEY` / `GEMINI_API_KEY` / `DOUBAO_API_KEY`），model 选择只走 `ai_summary.models`，MUST NOT 在代码 hardcode 或用 env 配 model。模型配置 MUST 兼容旧字符串格式（直接填写 model id）与对象格式（至少含 `model`，可含后端特定请求选项）；Grok 的默认对象格式 MUST 显式配置 `reasoning_effort`。

**Lock**: user-confirmed
**Confirmed-At**: 2026-07-09

#### Scenario: defaults/routing.yaml 含 ai_summary 段
- **WHEN** 读取 `defaults/routing.yaml`
- **THEN** 文件顶层存在 `ai_summary:` 段，含 `enabled`、`selection_order`、`fallback_on_no_key`、`models` 四个键；`models.<backend>` 下含 `fast` / `deep` 两档模型配置

#### Scenario: Grok 默认档位含推理强度
- **WHEN** 读取 `defaults/routing.yaml` 的 `ai_summary.models.grok`
- **THEN** `fast` 档配置为 `model: grok-4.3` 且 `reasoning_effort: low`
- **THEN** `deep` 档配置为 `model: grok-4.5` 且 `reasoning_effort: medium`

#### Scenario: 硬规则优先级高于 AI 综述
- **WHEN** query 命中临床研究 / 专利 / 官方文档等硬规则
- **THEN** ROUTING 起点表的 AI 综述层 MUST 被跳过，按硬规则派 site-search

#### Scenario: 用户禁用 AI 综述层
- **WHEN** 用户改 `~/.config/search-crew/routing.yaml` 中 `ai_summary.enabled: false`
- **THEN** 所有 subagent 都不调用 AI backend，回到原有 jina/serper 路径

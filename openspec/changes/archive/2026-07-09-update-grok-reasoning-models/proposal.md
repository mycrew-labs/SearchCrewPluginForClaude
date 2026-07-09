## Why

xAI 已将旧 Grok fast 模型迁移到 `grok-4.3` 配低推理强度，并发布 `grok-4.5` 作为新的通用高能力模型。当前配置只能表达模型名，无法明确控制 Grok 的推理强度，容易让快档成本与延迟依赖服务端默认行为。

## What Changes

- 将 Grok 默认快档改为 `grok-4.3`，并显式设置 `reasoning_effort: low`。
- 将 Grok 默认深档改为 `grok-4.5`，并显式设置 `reasoning_effort: medium`。
- 让 `ai_summary.models.<backend>.<tier>` 兼容字符串旧格式与对象新格式；对象格式可携带 `model` 和后端特定请求选项。
- xAI 请求体在配置了推理强度时发送 `reasoning: {effort: ...}`。
- 更新相关测试与文档，说明模型仍由 `routing.yaml` 管理，密钥仍只走环境变量。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `orchestration`: `ai_summary.models` 的 Grok 档位从单纯 model id 扩展为可配置 model id 与推理强度。
- `fast-search`: `/search-fast` 使用 Grok 快档时需要透传低推理强度。

## Impact

- 影响 `defaults/routing.yaml` 与用户态 seed 后的配置形态说明。
- 影响 `skills/search-toolkit/scripts/lib/ai_summary.py` 的模型配置解析，以及 `ai_grok.py` 的请求体。
- 影响 `search.py`、`ai_search.py` 与现有 AI backend 接口测试。
- 影响 `README.md`、`EXTENDING.md`、`openspec/specs/*` 中关于 Grok 默认模型与配置结构的描述。

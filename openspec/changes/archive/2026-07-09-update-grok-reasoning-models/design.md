## Context

AI 综述层当前从 `routing.yaml` 读取 `ai_summary.models.<backend>.<tier>`，值是单个模型名字符串。这个结构可以替换模型，但不能表达 xAI 对 Grok 退役 fast 模型给出的替代方式：同一模型配指定推理强度。

Grok backend 已走 Responses API，请求体已有集中构造点；因此本次只需要扩展配置解析和 xAI 请求参数，不需要改搜索结果封装、引用解析或调用上限逻辑。

## Goals / Non-Goals

**Goals:**

- Grok 快档默认使用 `grok-4.3` 和 `reasoning_effort: low`。
- Grok 深档默认使用 `grok-4.5` 和 `reasoning_effort: medium`。
- `ai_summary.models` 对旧字符串格式保持兼容。
- 推理强度只在支持该参数的 Grok backend 中发送，不影响 gemini / doubao。

**Non-Goals:**

- 不改变 AI backend 的选择顺序、默认引擎策略或 key 管理方式。
- 不修改用户已存在的 active 配置文件。
- 不引入新的命令行参数；`--model` 仍只覆盖模型名。

## Decisions

- **模型配置解析返回结构化配置。** `resolve_model` 继续保留为兼容入口，同时新增结构化解析，让调用链能拿到 `model` 与 `reasoning_effort`。这样旧测试和旧调用方不必一次性重写。
- **配置格式采用渐进式对象格式。** 旧格式 `fast: grok-4.3` 仍有效；新格式 `fast: {model: grok-4.3, reasoning_effort: low}` 仅在需要后端选项时使用。相比新增平行字段，这种写法把同一档位的参数放在一起，减少错配。
- **Grok backend 显式接收推理强度。** `ai_grok.search()` 增加可选参数，只有传入值时才写入 `body["reasoning"]`，避免影响未配置或旧配置用户。

## Risks / Trade-offs

- 旧用户 active 配置仍可能保留 `grok-4-fast` → 运行时保持兼容；文档提示重新 seed 或手动迁移。
- `--model` 只能覆盖模型名，不能覆盖推理强度 → 保持现有命令行边界；需要指定推理强度时改配置文件。
- xAI 对不同模型支持的推理强度语义可能继续变化 → 配置层只透传，不在代码硬编码具体模型判断。

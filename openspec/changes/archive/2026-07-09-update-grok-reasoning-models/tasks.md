## 1. 配置与解析

- [x] 1.1 更新 `defaults/routing.yaml` 的 Grok 默认档位为对象格式，快档 `grok-4.3/low`，深档 `grok-4.5/medium`
- [x] 1.2 扩展 AI 综述模型配置解析，兼容字符串旧格式和对象新格式
- [x] 1.3 调整 `search.py` 与 `ai_search.py` 调用链，传递结构化模型配置

## 2. Grok 请求

- [x] 2.1 让 `ai_grok.search()` 接收可选 `reasoning_effort`
- [x] 2.2 xAI Responses 请求体在配置推理强度时写入 `reasoning.effort`

## 3. 测试与文档

- [x] 3.1 更新或新增单元测试，覆盖 Grok 对象格式解析与请求体
- [x] 3.2 更新 README / EXTENDING / 相关规格说明中的 Grok 默认模型与推理强度描述
- [x] 3.3 运行受影响测试与 OpenSpec 校验

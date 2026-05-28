## Why

`/search-fast` 现在返回「一段综述 + 一坨扁平 URL 列表」，用户看不出哪条结论对应哪个源、无法逐条核对原始资料。

实测三家 AI backend 的引用元数据（2026-05-29 真实调用）：

| backend | 偏移 | 实测字段 |
|---|---|---|
| grok | ✅ | `url_citation` 含 `start_index` / `end_index`（锚到正文字符区间） |
| gemini | ✅ | `groundingSupports[]`：`segment{endIndex, text}` + `groundingChunkIndices`（段→源） |
| doubao | ❌ 无偏移 | 但含 `site_name` / `publish_time` / `summary` 富元数据 |

结论：grok / gemini **能**做精确逐条脚注；doubao（中文默认源）**给不了偏移**，只能给富信息来源列表。设计 MUST 按 backend 能力区别对待，不假设统一。

## What Changes

- **保留引用偏移**：`ai_common.parse_responses_api` 把 grok 的 `start_index` / `end_index` 一并捞进 citation；`ai_gemini` 捞 `groundingSupports` 的 `segment`（endIndex/text）+ `groundingChunkIndices`。doubao 无偏移则照旧（带 site_name / publish_time）。
- **ai_search 渲染脚注**：当 backend 提供偏移时，在 summary 对应位置插 `[n]` 标记，并产出编号来源列表（`[n] 标题 — url`）；无偏移时回落「综述 + 末尾富信息来源列表」。输出加 `summary_cited`（带 `[n]` 的正文）+ `sources`（编号列表）。
- **`/search-fast` 命令**：呈现 `summary_cited` + 编号来源，使能做脚注的（grok/gemini）逐条可点；做不了的（doubao）给清晰来源列表。
- 诚实标注：脚注是"模型声明引了此源"，非逐字可考；要逐条锚到原文段落用 `/search-deep`（evidence-search anchor）。

## Capabilities

### Modified Capabilities

- `fast-search`：ADD「/search-fast 综述按 backend 可得的引用偏移渲染逐条脚注；无偏移 backend（如 doubao）回落富信息来源列表」。

## Impact

- **代码**：`ai_common.parse_responses_api`（capture 偏移）、`ai_gemini`（capture grounding 段偏移）、`ai_search`（脚注渲染 + sources 输出）、`commands/search-fast.md`（呈现脚注 + 来源）。
- **无 locked 行为破坏**：fast-search 现有「summary + citations」不变，只是更丰富的呈现（内联脚注）+ 输出加字段；属增强。
- **按 backend 差异**：grok/gemini 精确脚注，doubao 来源列表——文档与命令明确这点，不误导用户以为中文也逐行可考。
- **测试**：ai_common 偏移解析、ai_search 脚注渲染（有偏移→插标记；无偏移→列表）单测。

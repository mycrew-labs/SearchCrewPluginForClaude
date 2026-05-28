## Why

`fast-search` 现在把两件目标冲突的事揉在一起：①「快出答案」②「结构化循证采集」。实测一次 `/search-fast` ~3 分钟——慢的不是搜索（jina `--with-content` 仅 2.4s），而是 haiku 把 17 万字正文**重写**成 5 个 ranked 产物文件。

参考灵感来源 smart-search 的设计：它默认**一个 AI 综述源直接出答案**（一次调用 ~12-28s），只在答案不足时才补原始源。我们当初借鉴时拿了 AI backends / call-cap / 搜索摘要，却没拿它"AI 答案优先"的核心路由，保留了 fast-search 的"证据优先、永远结构化"——这就是慢的根。

拆开后两者各自纯粹：要快问快答的走 AI 综述；要循证证据的走结构化采集（deep/wide 的工人）。

## What Changes

- **`/search-fast` 改为「AI 综述快答」，且不经 subagent**：主 agent 直接跑 `search.py --prefer ai --tier fast`（一次 AI 调用、~12-28s 出综述 + citations），呈现给用户。无结构化产物、无 haiku 二次消化。AI backend 按语言/语境选（中文→doubao、全球英文→gemini、X/实时→grok），沿用 routing.yaml selection_order。去 subagent 化是为最快（省 subagent 启动开销）。
- **现 `fast-search` subagent 重命名为 `evidence-search`**：行为不变（jina `--with-content` + ranking + 关键词 + INDEX + anchor 的低成本 haiku 结构化采集工），**专供 deep / wide 派发**调用。承载 USER_DESIGN 的「数据关联 + 循证传递」价值。
- **deep / wide 改派 `evidence-search`**：两个 lead 的派发引用从 `fast-search` 改为 `evidence-search`（`SEARCH_CREW_SUBAGENT` 值、Task subagent_type、prompt 文案）。
- **能力 spec 重组**：`fast-search` 能力的 6 条结构化-worker 需求**迁移**到新能力 `evidence-search`（行为不变、重新落锁）；`fast-search` 能力转为描述「`/search-fast` = AI 综述快答、无 subagent」。
- **文件**：`agents/fast-search.md` → `agents/evidence-search.md`；`commands/search-fast.md` 重写为主 agent 直连 AI 综述流程；deep/wide agent prompts 改引用；测试里 `fast-search` 字样按需更新。

## Capabilities

### Modified Capabilities

- `orchestration`：MODIFY `/search-fast` 语义——从「派 fast-search subagent」改为「主 agent 直连 AI 综述快答（不经 subagent）」；deep/wide 内部派 `evidence-search`（非 fast-search）。
- `fast-search`：能力**重定义**——从「结构化单轮采集 subagent」改为「`/search-fast` 的 AI 综述快答路径（主 agent 直连，无 subagent，无结构化产物）」。原 6 条结构化-worker 锁定需求 REMOVE（迁往 evidence-search）。

### New Capabilities

- `evidence-search`：低成本（haiku）结构化循证采集 subagent——jina `--with-content` 一次带正文、ranking + 推荐等级 + 关键词、产物以 subagent 名为前缀、零 key 回落 WebSearch/WebFetch、不做站内精确搜索/多轮、查询词遵循「主题+目标+限定」。供 deep/wide 派发。（即原 fast-search 行为，整体迁移 + 重新落锁。）

## Impact

- **blast radius 大**：重命名一个 locked 能力 + 改 `/search-fast` 语义 + deep/wide 派发引用 + agent 文件改名 + 测试。需逐一确认。
- **locked 影响**：`fast-search` 的 6 条 user-confirmed 锁定需求随能力重组而迁移到 `evidence-search`（行为不变，等同"换个能力名重新落锁"）；`/search-fast` 在 orchestration 的语义需 MODIFY。归档前按锁确认 gate 逐条确认。
- **成本/速度**：`/search-fast` 从 ~3min 降到 ~12-28s（一次 AI 调用）；evidence-search 仍是 deep/wide 的廉价工人，速度不变（它本就该慢点、换结构化证据）。
- **向后兼容**：deep/wide 对外行为不变（内部 worker 换名）；`/search-fast` 的产物形态变了（不再有 5 个文件，改为一段综述 + citations）——这是有意的语义变更。
- **未决**：`evidence-search` 是否给一个低调的 `/search-evidence` 显式命令，还是只内部供 deep/wide + 语义自动触发（倾向后者，少占命令名）。

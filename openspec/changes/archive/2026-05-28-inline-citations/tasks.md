## 1. 捞引用偏移（lib/backends）

- [x] 1.1 `ai_common.parse_responses_api`：citation dict 保留 `start_index` / `end_index`（grok 有；doubao 无则不带）——现在被丢弃
- [x] 1.2 `ai_gemini`：捞 `groundingSupports[]` 的 `segment.endIndex`（及 text）+ `groundingChunkIndices`，构造「段→源」映射；citations 仍含 url/title

## 2. ai_search 渲染脚注

- [x] 2.1 `ai_search.py`：若 citations 带偏移（grok）或有 grounding 段映射（gemini）→ 在 summary 插 `[n]` 标记，产出 `summary_cited` + 编号 `sources`
- [x] 2.2 无偏移（doubao）→ 不插标记，输出富信息 `sources`（url/title/site_name/publish_time），`summary_cited` 置空或等于 summary
- [x] 2.3 输出 schema 加 `summary_cited`、`sources`（保留原 `summary`、`citations` 兼容）

## 3. 命令呈现

- [x] 3.1 `commands/search-fast.md`：回复用 `summary_cited`（有则）+ 编号 `sources`；说明脚注是"带出处速览"，逐条原文级循证走 /search-deep

## 4. 测试

- [x] 4.1 `ai_common` 偏移解析单测（含偏移 / 不含偏移两路）
- [x] 4.2 `ai_search` 脚注渲染单测：有偏移→插 `[n]` + sources；无偏移→纯 sources 列表
- [x] 4.3 全量 unittest

## 5. 验证 + 归档

- [x] 5.1 `openspec validate inline-citations --strict`
- [x] 5.2 完工简报：fast-search ADD 一条（按 backend 能力渲染来源）拟落锁；确认 → bump → archive → commit → push
- [ ] 5.3 **manual** reload 实测：grok/gemini 出脚注、doubao 出来源列表

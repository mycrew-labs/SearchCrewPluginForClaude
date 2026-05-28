---
name: search-toolkit
description: Search Crew 的搜索 / 抓取 / 站点 API / 产物组织工具包。供 fast-search / site-search / deep-search 三个 subagent 复用。零依赖 Python stdlib。
---

# search-toolkit

供 Search Crew subagent 调用的工具集。所有脚本都遵循统一 JSON CLI 契约，方便从 Bash 调起。

> **backend 是当前实现，不是本 skill 的身份**。当前 backend 包括 Jina / Serper（通用搜索 + 抓取）、grok / gemini / doubao（AI 综述）、GitHub / MDN / Algolia 等站点适配器（精确搜索）。未来可替换 / 增加任意 backend，本 skill 的接口契约（统一 JSON 输出、`lib/_http.py` 出口打点、产物组织约定）保持不变。

## 启动强制预检（site-search 必做）

site-search subagent 接到任务后、调用任何 backend 或 MCP **之前** 必跑：

1. `python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/site_search.py --list-adapters` 查实时适配器清单
2. 确认目标站是否已有 adapter
3. 若已有，确认 adapter status（`✅` / `⚠️ best-effort` / `降级`）

跳过预检直接拼调用参数 = 缺陷。`--list-adapters` 输出快照应在工作日志里留痕。

## 路径

所有脚本：`$CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/`。

## CLI 入口

| 脚本 | 用途 | 关键参数 |
|---|---|---|
| `search.py` | 通用搜索 | `--query`、`--max-results`、`--language`、`--prefer jina\|serper\|ai`、`--with-content`（jina 一次带回正文，省单独抓页） |
| `fetch.py` | URL → markdown | `<url>` |
| `site_search.py` | 站点搜索（API 适配器优先） | `--site`、`--query`、`--max-results`；`--list-adapters` 列清单 |
| `check_backends.py` | 检查 backend / Chrome / MCP 状态 | 无参数 |
| `seed_user_config.py` | 拷贝 defaults → `~/.config/search-crew/`；`--merge` 补缺失顶层段（`--dry-run` 只检测） | 无参数（首次安装 / 兜底）；`--merge [--dry-run] [--trigger <来源>]` |
| `promote.py` | 把一条 pending 候选晋升进 active（pending→active 唯一合规途径） | `<pending-file>` `[--trigger]` |
| `run_paths.py` | 打印本次 run 的规范目录（subagent 未拿到 target_dir 时调它，**别自己编 session_id**） | `[--subagent <name>]` |
| `stop_hook.py` | Stop 事件扫 pending 提示 | 通过 stdin 接 hook input |
| `finalize_usage.py` | 聚合 usage.jsonl → usage-summary.md | `<run_root>`；`--subagent <name>` 切片 |
| `usage.py` | 跨 run 用量查询（用户用 `!` 跑） | `--last N` / `--by-day` / `--by-week` / `--by-month` / `--by-backend` / `--since` / `--raw` |

## 通用输出契约

### 成功

```json
{ "backend": "jina", "results": [{"title": "...", "url": "...", "snippet": "...", "extra": {...}}, ...] }
```

所有 backend 返回的 `results[*]` 统一 schema：`{title, url, snippet, extra}`。

### 失败 / fallback

```json
{ "backend": null, "results": [], "fallback": "WEBSEARCH_FALLBACK" }
{ "source": null, "fallback": "WEBFETCH_FALLBACK" }
{ "adapter": null, "hint": "...", "results": [] }
```

调用方收到 fallback marker 时改用 Claude Code 内置 WebSearch / WebFetch 工具。

### fetch.py 三态输出（web-page-fetch 用）

```json
{ "source": "jina-reader", "url": "...", "markdown": "...", "fallback": null }   // HTML 渲染
{ "source": "raw", "url": "...", "markdown": "<原文>", "fallback": null }         // raw 文件原文直取
{ "source": null, "markdown": null, "blocked": "anti_bot", "fallback": null }     // 反爬/验证码墙
{ "source": null, "markdown": null, "fallback": "WEBFETCH_FALLBACK" }             // 无 key/网络失败
```

- `source` 非 null → 用 markdown；`WEBFETCH_FALLBACK` → 内置 WebFetch；`blocked: anti_bot` → 诚实报「被风控拦截」，禁止解验证码、禁止当正文。
- HTML vs raw 靠**响应 Content-Type** 主导 + 无 HTML 标签兜底（不用 host/扩展名清单）。
- 读取/抓取操作**豁免站点调用上限**（上限只管搜索源）。

## Backend 路由起点（决策依据）

详见 [ROUTING.md](./ROUTING.md)。**Leader（主 agent / deep-search）按主题选择 backend，不要盲目降级**。

## 产物组织约定（P-DATA-001 / P-OUTPUT-001）

subagent 落盘时必须遵守：

1. 文件 / 子目录前缀以 subagent 名开头：`fast-search-*` / `site-search-*` / `deep-search-*`
2. 每个 subagent 必产 wiki 风格 `INDEX.md`（含子文件简介、ranking、推荐与否、关键词清单）
3. 单 markdown 头部 YAML front-matter 含 `keywords`、`url`、`ranking`、`recommended`
4. 关键片段用 `### anchor: <slug>` 标记，供报告 / 摘要按 anchor 引用
5. 附件统一 `<run_root>/attachments/<sha256[:12]>.<ext>`，markdown 用相对路径 `![](../attachments/<hash>.<ext>)`

`lib/output.py` 提供工具函数：

- `attachment_path(run_root, content, ext)` → 附件去重写盘
- `write_front_matter(keywords, **extra)` → 生成 YAML front-matter
- `evidence_anchor(slug)` → 生成 anchor markdown
- `render_index_md(...)` → 生成 INDEX.md 模板

## Usage 打点（P-USAGE-*）

`lib/_http.py` 出口自动调 `lib/usage.py:record(...)`，业务代码**禁止**绕过自己写 jsonl。打点字段见 [TECH T-USAGE-002](../../openspec/changes/add-usage-tracking/TECH.md)。

subagent 结束前必须调：

```bash
python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/finalize_usage.py --subagent <name> <run_root>
```

主 agent 在最终回复前调一次全局聚合：

```bash
python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/finalize_usage.py <run_root>
```

主 agent 给用户的回复**只一行** cost 总览（详见 commands/deep-search.md）。

## 错误处理

- HTTP 4xx / 解析错误 → `BackendError(retryable=False)`，调用方放弃
- HTTP 429 / 5xx / 超时 → `BackendError(retryable=True)`，调用方可重试或降级
- 无 key / 全部 backend 不可用 → 进程退出 0 + `fallback` 字段标 marker

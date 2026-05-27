## Why

两件事整理插件的「对外接口面」：

1. **公开 fetch 能力**：`fetch.py` 是个比内置 WebFetch 更强的页面读取器（Jina Reader 渲染 JS、产出干净 markdown、走 `lib/_http.py` 的 call-cap + usage 打点），但现在只锁在 fast/site/deep-search subagent 内部。把它公开成一个 skill，让**主 agent** 读网页 / 文件时优先用它，对标并接管内置 WebFetch。这个 skill 是一个会**持续增强**的能力底座（首版即要求 HTML + raw 两类都支持）。
2. **命令改名**：`setup` / `deep-search` 命令名太通用，会以裸名冒在全局命令面板（`/setup`、`/deep-search`），对其他插件不友好。归入 `search-*` 命名体系。

## What Changes

- **新增 `web-page-fetch` skill**（`skills/web-page-fetch/SKILL.md`，能力名 `web-page-fetch`）：主 agent 读任意 URL 时 SHALL 优先调 `fetch.py`；仅当拿到 `WEBFETCH_FALLBACK` marker（无 key / 抓取失败）才回落内置 WebFetch。
- **`fetch.py` 增强：兼容 raw 文件**。除 HTML 页面（走 Jina Reader → markdown）外，对 raw 文本资源（如 `https://raw.githubusercontent.com/.../README.md`、`.md` / `.txt` / `.json` / 源码等）MUST 直接取原文返回，**不经** Jina Reader 处理（避免把纯文本/代码当 HTML 渲染破坏内容）。HTML vs raw 的判定走「响应 Content-Type 主导 + 无 HTML 标签兜底」（不用 host / 扩展名清单，兼容性差）。
- **命令改名**：`commands/setup.md` → `search-skill-setup`、`commands/deep-search.md` → `search-deep`（仅这两个 slash 命令；subagent 名、`<run_root>/deep-search/` 产物路径、`SEARCH_CREW_SUBAGENT` 值一律**不动**）。
- **改 locked 规格**：`orchestration`（slash 命令名 + 主 agent 优先 plugin fetch）、`config-lifecycle`（`/setup` 引用改名）——归档前按「锁确认 gate」逐条提请用户确认。

## Capabilities

### New Capabilities

- `web-page-fetch`：主 agent 优先用的页面 / 文件读取能力。首版支持 HTML（Jina Reader 渲染）+ raw 文件（原文直取）两类，零 key 回落内置 WebFetch；设计为可持续增强（未来可加更多源类型 / 解析器）。

### Modified Capabilities

- `orchestration`：(1) 唯一显式 slash 命令名 `/deep-search` → `/search-deep`；(2) 新增「主 agent 读 URL 时优先用 web-page-fetch skill，而非直接用内置 WebFetch」的行为
- `config-lifecycle`：onboarding 备份提示里的 `/setup` → `/search-skill-setup`

## Impact

- **代码**：新增 `skills/web-page-fetch/SKILL.md`；`fetch.py` 增 raw 分支（HTML/raw 判定 + raw 原文直取，仍经 `lib/_http.py`）；`commands/setup.md`、`commands/deep-search.md` 改名 + frontmatter `name`
- **文档**：`README.md`（安装 + 触发表的命令名 + 新 fetch skill）、`tests/MANUAL.md`、各处命令引用、`EXTENDING.md`（fetch skill 如何增强）
- **locked spec**：2 处（orchestration / config-lifecycle），归档前确认
- **测试**：fetch.py raw 分支加单测（mock raw URL 响应）
- **向后兼容**：fetch.py 现有 HTML 行为不变，raw 是新增分支；subagent 对 fetch.py 的调用不受影响；命令改名后旧 `/setup` `/deep-search` 不再存在（用户需用新名）

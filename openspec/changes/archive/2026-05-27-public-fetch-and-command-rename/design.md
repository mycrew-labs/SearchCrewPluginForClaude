# Design — public-fetch-and-command-rename

## Context

- `fetch.py` 现状：单一路径 `jina.fetch(url)`（Jina Reader，HTML→markdown），失败 → `WEBFETCH_FALLBACK`。返回 `{source, url, markdown, anonymous, fallback}`。被 fast/site/deep-search subagent 调用。
- 本次要：(1) 让**主 agent** 也能用这个能力（公开成 skill，对标内置 WebFetch）；(2) `fetch.py` 兼容 raw 文件；(3) 实测发现的反爬假成功必须修；(4) 命令名归入 `search-*`。
- 实测数据（本会话）：WeChat 公众号两篇都被风控墙挡住——Jina 返回「环境异常」验证页**当成功返回**（假正文），Chrome MCP 重定向到滑块验证码。这直接定义了「反爬识别 + 诚实失败」的硬需求。

## Goals / Non-Goals

**Goals:**

- `web-page-fetch` skill：主 agent 读任意 URL 时优先走 `fetch.py`，零 key 才回落内置 WebFetch
- `fetch.py` 支持 raw 文件（原文直取，不经 Jina Reader）+ HTML（Jina Reader 渲染）两类
- `fetch.py` 识别反爬/验证码页 → 判失败（不把验证页当正文）
- 命令 `setup`→`search-skill-setup`、`deep-search`→`search-deep`
- 把 fetch skill 设计成**可持续增强**的底座（输出契约 + 内部分派留扩展点）

**Non-Goals:**

- 不实现 WeChat 公众号抓取（风控 + 滑块，合规手段过不去；文档标已知不支持）
- 不解任何验证码（browser-control 红线）
- 不改 subagent 名 / `<run_root>/deep-search/` 路径 / `SEARCH_CREW_SUBAGENT` 值
- 不重写现有 Jina Reader HTML 路径（raw / 反爬是新增分支）

## Decisions

### D-1 HTML vs raw 判定：Content-Type 主导，无 HTML 标签兜底

**不用** raw-host / 扩展名清单（兼容性差、维护负担）。改成「先直连看 Content-Type」：

`fetch.py` 流程：

1. **直连 GET 一次**：`lib/_http` 取 URL 的 body + 响应 `Content-Type`（需给 `_http` 加一个返回 `(text, content_type)` 的取法；现有 `request_text` 只回 text）。
2. **反爬检查**（D-2）：先对 body 跑反爬签名；命中 → 直接判 `anti_bot_blocked`，不再往下。
3. **按 Content-Type 判定**：
   - `text/html` / `application/xhtml+xml` → **HTML**：URL 二次送 Jina Reader（`jina.fetch`）渲染（JS 页面、干净 markdown），`source: "jina-reader"`
   - `text/plain` / `text/markdown` / `application/json` / `text/*`（非 html）/ 源码类 / `application/xml` 等 → **raw**：直接返回第 1 步的 body 原文，`source: "raw"`，不送 Jina
4. **兜底（Content-Type 缺失 / 含糊，如 `application/octet-stream`、无 header）**：检查 body 有没有 HTML 标签（`<!doctype html`、`<html`、`<head`、`<body` 等）；**无 HTML 标签** → 当 raw 返回原文；**有** → 当 HTML 送 Jina Reader。

**取舍**：HTML 页面会发 2 次请求（直连探测 + Jina 渲染）。这是「不靠 URL 猜、纯 Content-Type 判」的固有代价，可接受——第 2 次 Jina 渲染本来就是 HTML 必需的（直连 body 没 JS 渲染）。raw 文件只 1 次请求。
**为什么不 HEAD 探测**：HEAD 对 raw 反而多一次请求（HEAD + GET）；直接 GET 一次拿 body+type 最省。

### D-2 反爬 / 验证码识别：内容签名 → 判失败，不当正文

抓回内容（raw 或 HTML 路径都过）后，扫描反爬签名；命中即判 `anti_bot_blocked`，**不返回该内容当正文**：

签名（保守，避免误杀）：需**同时**满足「短内容（如 < 1500 字）」+ 命中下列任一短语：
- `环境异常`、`完成验证后即可继续访问`、`去验证`
- `requiring CAPTCHA`、`拖动下方滑块`、`滑块`、`captcha`（大小写不敏感）

**为什么要「短内容 + 短语」双条件**：避免一篇正常讲「验证码技术」的长文被误判。验证墙页都很短（实测 600-900 字）且含上述强信号。

命中 → 输出 `blocked: "anti_bot"`（见 D-3 契约），由调用方诚实报「被风控拦截，未取正文」。

### D-3 fetch.py 输出契约（扩展，向后兼容）

| 场景 | 输出 |
|---|---|
| HTML 成功 | `{source: "jina-reader", url, markdown, anonymous, fallback: null}`（**不变**） |
| raw 成功 | `{source: "raw", url, markdown: <原文>, fallback: null}`（新增 source 值） |
| 反爬拦截 | `{source: null, url, markdown: null, fallback: null, blocked: "anti_bot"}`（**新增**，**不**给 WEBFETCH_FALLBACK） |
| 无 key / 网络失败 | `{source: null, url, markdown: null, fallback: "WEBFETCH_FALLBACK"}`（**不变**） |

**关键**：反爬拦截**不**走 `WEBFETCH_FALLBACK`——因为内置 WebFetch 对同一道墙同样无能（且会再骗一次）。反爬是独立终态，调用方据此诚实失败。现有只判 `WEBFETCH_FALLBACK` 的 subagent 代码不受影响（向后兼容）。

### D-4 web-page-fetch skill：主 agent 优先用 + 三态分派

新增 `skills/web-page-fetch/SKILL.md`。description 触发面：「用户给 URL 要读 / 总结 / 抽取页面或文件内容」时主 agent 优先用本 skill，而非直接 WebFetch。skill 指示主 agent：

1. 调 `python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/fetch.py <url>`
2. 按输出分派：
   - `source` 非 null（jina-reader / raw）→ 用返回的 markdown
   - `fallback: "WEBFETCH_FALLBACK"` → 改用内置 WebFetch
   - `blocked: "anti_bot"` → **诚实报**「该页被风控/验证码拦截，未取到正文」；**MUST NOT** 解验证码；对非验证码的 SPA/登录墙可建议升级 browser-control（但验证码墙不行）
3. 已知不支持：WeChat 公众号（`mp.weixin.qq.com`）——直接告知用户不可抓，别反复试

**与内置 WebFetch 的关系**：本 skill 是「优先选择」，不是物理禁用 WebFetch；零 key / fetch.py 失败时仍回落 WebFetch。「优先」靠 skill description + 指令实现（Claude Code 无法物理拦截内置工具）。

### D-5 命令改名

- `commands/setup.md` → `commands/search-skill-setup.md`，frontmatter `name: search-skill-setup`
- `commands/deep-search.md` → `commands/search-deep.md`，frontmatter `name: search-deep`
- 命令正文里「派 deep-search subagent」等 subagent 引用**不动**（subagent 名没变）
- 全量改文档中的**命令调用**引用（README / MANUAL / 互引），但**不动** `<run_root>/deep-search/` 路径

### D-6 locked 规格编辑（归档前按锁确认 gate 逐条确认）

1. `openspec/specs/orchestration/spec.md`：
   - 「唯一显式 slash command 是 `/deep-search`」requirement → `/search-deep`（标题 + 正文 + scenario）
   - 新增 requirement：主 agent 读 URL 优先用 web-page-fetch skill（这条是 ai-derived 新增，但因与 locked 的 slash-command 同文件，一并提请确认）
2. `openspec/specs/config-lifecycle/spec.md`：onboarding 备份提示的 `/setup` → `/search-skill-setup`

### D-7 调用上限豁免读取操作（实施期发现的前置 bugfix）

实施第 1 步发现：已上线的 call-cap 按 `(run_id, backend)` 计数，把 jina-search 与 jina-reader 混算，非 AI 上限 2 次 → 同 run 抓 >2 个页面被拦，**打断 fast-search「抓 top N」**。用户拍板**选项 B：读取/抓取操作完全豁免上限，上限只管搜索源**。

实现：`_http.request_json` / `request_text` 加 `cap_exempt: bool = False` 参数；`_check_and_increment_cap` 在 `cap_exempt=True` 时直接跳过（不计数、不拦截）。

- **豁免（cap_exempt=True）**：`jina.fetch`（jina-reader）、`fetch.py` 直连探测
- **仍计数（默认）**：`jina.search`、`serper.search`、grok/gemini/doubao、站点搜索 adapter

对应 usage-tracking locked 需求「站点调用上限」加 MODIFIED delta（措辞加豁免，归档前按 gate 确认）。

### D-8 被挡不直接放弃：needs_auth 细分 + on_blocked 策略 + 远程插入点

用户指出：反爬/被挡 ≠ 直接放弃，高价值内容（付费 paper PDF、登录墙）应拉用户一起拿。决策：

- **blocked 细分**：`anti_bot`（验证码/风控，内容签名）+ `needs_auth`（登录/付费，HTTP 401/403）。
- **on_blocked 策略**（`limits.yaml` `web_page_fetch.on_blocked`，默认 `honest`）：`honest` = 诚实失败不打扰；`collaborate` = 诚实说明 + 给协作路径（贴正文 / 本地文件 / cookies）。fetch.py 把策略透传进 blocked 输出，主 agent 据此行动。
- **远程插入点（B-006，本期不实现）**：未来 needs_auth 先自动走远程 browser-host（OpenCLI + HTTP API + 私有 overlay，用登录态会话拿），仍拿不到才落 on_blocked。架构上 blocked → [远程] → on_blocked，已留好位置。

**为什么 setup 预配而非每次问**：用户拍板——每次协作太烦、可能莫名打断自动流程；提前在 setup 配好策略，运行时不打断。

## Risks / Trade-offs

- **反爬签名误杀**：正常长文含「验证码」字样被误判。**缓解**：双条件（短内容 + 强信号短语），签名清单保守可扩。
- **raw 判定靠 Content-Type，服务器给错 type 会误判**：少数服务器对 .md 返 `text/html` 或对页面返 `text/plain`。**缓解**：无 HTML 标签兜底纠偏（D-1 第 4 步）；接受极少数边界。
- **HTML 双请求**：直连探测 + Jina 渲染两次请求。**缓解**：raw 只 1 次；HTML 第 2 次是渲染必需，可接受。
- **「优先用」非强制**：主 agent 仍可能直接用内置 WebFetch（skill 是软引导）。**缓解**：description 写清楚 + 在 orchestration spec 立 requirement；接受无法物理拦截。
- **命令改名破坏旧调用**：用户习惯的 `/setup` `/deep-search` 不再存在。**缓解**：文档全量更新；这是一次性迁移，可接受。

## Migration Plan

1. `fetch.py` 加 raw 分支 + 反爬识别（向后兼容，subagent 不受影响）。
2. 新增 `skills/web-page-fetch/SKILL.md`。
3. 命令文件改名 + 文档引用更新。
4. locked 规格编辑（归档前确认）。
5. 回滚：删 skill + revert fetch.py 分支 + 命令改回旧名。

## Open Questions

（已收口）

- ~~raw 用 host / 扩展名清单？~~ → **否**，改 Content-Type 主导 + 无 HTML 标签兜底（D-1）。用户拍板：清单兼容性差、维护负担。
- ~~暴露 `/search-fetch` 命令给用户手动调？~~ → **否**，只做 skill。用户拍板：不会有手动命令需求。

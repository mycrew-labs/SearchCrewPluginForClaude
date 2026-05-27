# web-page-fetch Specification

## Purpose
TBD - created by archiving change public-fetch-and-command-rename. Update Purpose after archive.
## Requirements
### Requirement: 主 agent 读 URL 优先用 web-page-fetch，零 key 才回落内置 WebFetch
当用户给出具体 URL 要求读取 / 总结 / 抽取页面或文件内容时，主 agent SHALL 优先调用 `fetch.py`（经 `web-page-fetch` skill 指引），而非直接用内置 WebFetch。仅当 `fetch.py` 返回 `WEBFETCH_FALLBACK` marker（无 key / 网络失败）时，才改用内置 WebFetch。

#### Scenario: 读普通网页优先走 fetch.py
- **WHEN** 用户说「读一下这个页面：https://example.com/article」
- **THEN** 主 agent 调 `python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/fetch.py <url>`，用其返回的 markdown，而非直接调内置 WebFetch

#### Scenario: 零 key 回落内置 WebFetch
- **WHEN** `fetch.py` 返回 `{"fallback": "WEBFETCH_FALLBACK"}`
- **THEN** 主 agent 改用内置 WebFetch 完成读取

### Requirement: fetch.py 按 Content-Type 区分 HTML 与 raw
`fetch.py` SHALL 先直连 GET 目标 URL 拿到 body 与响应 `Content-Type`，据此判定：`text/html` / `application/xhtml+xml` 走 Jina Reader 渲染（`source: "jina-reader"`）；`text/plain` / `text/markdown` / `application/json` / 其他 `text/*` 非 html / 源码类 / `application/xml` 等直接返回原文（`source: "raw"`，不经 Jina Reader）。Content-Type 缺失或含糊时，MUST 用「body 是否含 HTML 标签」兜底判定。MUST NOT 靠 URL host / 扩展名清单判定。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-26

#### Scenario: raw 文件原文直取
- **WHEN** fetch.py 抓 `https://raw.githubusercontent.com/owner/repo/main/README.md`，响应 Content-Type 为 `text/plain`
- **THEN** 返回 `{"source": "raw", "markdown": <文件原文>, "fallback": null}`，内容不经 Jina Reader 处理

#### Scenario: HTML 页面走 Jina Reader 渲染
- **WHEN** fetch.py 抓一个 `text/html` 页面
- **THEN** 该 URL 二次送 Jina Reader，返回 `{"source": "jina-reader", "markdown": <渲染后 markdown>}`

#### Scenario: Content-Type 含糊时按有无 HTML 标签兜底
- **WHEN** 响应 Content-Type 缺失 / 为 `application/octet-stream`，且 body 不含 `<html` / `<body` / `<!doctype` 等 HTML 标签
- **THEN** 当 raw 返回原文

### Requirement: fetch.py 识别被挡页并判失败，区分 anti_bot 与 needs_auth，不当正文返回
`fetch.py` 抓回内容后 SHALL 识别两类「被挡」并判失败，MUST NOT 把被挡页当正文：
- **anti_bot**（验证码 / 风控墙）：内容**同时**满足「短内容（如 < 1500 字）」与「命中反爬强信号短语（`环境异常` / `完成验证后即可继续访问` / `去验证` / `requiring CAPTCHA` / `拖动下方滑块` / `captcha` 等，大小写不敏感）」→ 判 `anti_bot`。MUST NOT 走 `WEBFETCH_FALLBACK`（内置 WebFetch 对同一道墙同样无效）。
- **needs_auth**（登录墙 / 付费墙）：直连返回 HTTP 401 / 403 → 判 `needs_auth`。

被挡输出统一含 `on_blocked`（取自 `limits.yaml` 的 `web_page_fetch.on_blocked`，honest / collaborate），透传给主 agent：`{"source": null, "markdown": null, "blocked": "anti_bot"|"needs_auth", "on_blocked": "...", "fallback": null}`。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-26

#### Scenario: 微信验证墙判为 anti_bot
- **WHEN** fetch.py 抓微信公众号文章，Jina Reader 返回含「环境异常」「去验证」的短验证页
- **THEN** 返回 `{"blocked": "anti_bot", ...}`，不把验证页当正文

#### Scenario: 401/403 判为 needs_auth
- **WHEN** fetch.py 直连某 URL 返回 HTTP 403
- **THEN** 返回 `{"blocked": "needs_auth", "on_blocked": <策略>, "fallback": null}`，不走 WEBFETCH_FALLBACK

#### Scenario: 正常长文不被误判
- **WHEN** fetch.py 抓一篇正常讲解「验证码技术」的长文（含「captcha」字样但内容长、非验证墙）
- **THEN** 不判 anti_bot，正常返回正文（双条件中「短内容」不满足）

### Requirement: web-page-fetch 按 on_blocked 策略分派 + 已知不支持站点
`web-page-fetch` skill SHALL 指引主 agent 按 fetch.py 输出分派：(1) `source` 非 null → 用返回 markdown；(2) `fallback: WEBFETCH_FALLBACK` → 改用内置 WebFetch；(3) `blocked`（anti_bot / needs_auth）→ 按输出里的 `on_blocked` 策略处理：`honest` = 诚实告知未取到正文；`collaborate` = 诚实说明 + 按 blocked 类型给协作路径（needs_auth：浏览器登录后贴正文 / 本地文件路径 / cookies；anti_bot：浏览器过验证后贴正文）。任何情况 MUST NOT 解验证码、MUST NOT 把被挡页当正文。skill 文档 MUST 标注微信公众号（`mp.weixin.qq.com`）为已知不支持。未来 B-006 远程 browser-host 就绪后，needs_auth 先自动走远程，仍拿不到才落 on_blocked 策略（本期预留插入点，不实现）。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-26

#### Scenario: honest 策略诚实失败
- **WHEN** fetch.py 返回 `blocked: anti_bot, on_blocked: honest`
- **THEN** 主 agent 告知用户该页被拦截、未取到正文；不解验证码；不把被挡页当正文

#### Scenario: collaborate 策略给协作路径
- **WHEN** fetch.py 返回 `blocked: needs_auth, on_blocked: collaborate`（如付费 paper PDF）
- **THEN** 主 agent 诚实说明 + 建议用户「浏览器登录后贴正文 / 给本地文件路径 / 提供 cookies」，不直接放弃

#### Scenario: 微信公众号直接告知不支持
- **WHEN** 用户要求读 `https://mp.weixin.qq.com/s?...`
- **THEN** 主 agent 可直接告知「微信公众号已知无法抓取」，避免反复尝试


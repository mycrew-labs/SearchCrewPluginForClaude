# web-page-fetch Specification

## Purpose
TBD - created by archiving change public-fetch-and-command-rename. Update Purpose after archive.
## Requirements
### Requirement: 主 agent 读 URL 优先用 web-page-fetch，零 key 才回落内置 WebFetch

当用户给出具体 URL 要求读取 / 总结 / 抽取页面或文件内容时，主 agent SHALL 优先调用 `fetch.py`（经 `web-page-fetch` skill 指引），而非直接用内置 WebFetch。仅当 `fetch.py` 返回 `WEBFETCH_FALLBACK` marker（无 key / 网络失败）时，才改用内置 WebFetch。此优先由**双层**落实：(1) skill `description` 触发层（软引导，降低漏触发）；(2) PreToolUse hook 动作点兜底（见「PreToolUse hook 按清单分级拦截内置 WebFetch」需求）。`description` 与文档 MUST NOT 再声称「无法拦截内置工具」。

**Lock**: user-confirmed
**Confirmed-At**: 2026-06-14

#### Scenario: 读普通网页优先走 fetch.py
- **WHEN** 用户说「读一下这个页面：https://example.com/article」
- **THEN** 主 agent 调 `python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/fetch.py <url>`，用其返回的 markdown，而非直接调内置 WebFetch

#### Scenario: 零 key 回落内置 WebFetch
- **WHEN** `fetch.py` 返回 `{"fallback": "WEBFETCH_FALLBACK"}`
- **THEN** 主 agent 改用内置 WebFetch 完成读取

#### Scenario: 漏走 fetch.py 时被 hook 纠回
- **WHEN** 主 agent 未经 fetch.py、直接对一个 URL 发起内置 WebFetch
- **THEN** PreToolUse hook 拦截并提示改用 `fetch.py`，主 agent 据此改走正确路径

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

### Requirement: web-page-fetch 分派与升级路径
`web-page-fetch` skill SHALL 指引主 agent 以 `fetch.py --real-browser <url>` 作为读 URL 的统一入口，并按输出分派：(1) `source` 非 null → 用返回 markdown；(2) `fallback: WEBFETCH_FALLBACK` → 改用内置 WebFetch；(3) `blocked`（anti_bot / needs_auth）→ 按 `on_blocked` 策略处理：`honest` = 诚实告知未取到正文；`collaborate` = 诚实说明 + 按 blocked 类型给协作路径。任何情况 MUST NOT 解验证码、MUST NOT 把被挡页当正文。输出含 `warning` 字段时，主 agent MUST 向用户说明内容可能不完整。skill 文档 MUST NOT 再把微信公众号标注为不支持——该类站点经升级层抓取，升级层不可用时按 blocked 流程诚实处理。

**Lock**: user-confirmed
**Confirmed-At**: 2026-06-12

#### Scenario: honest 策略诚实失败
- **WHEN** fetch.py 返回 `blocked: anti_bot, on_blocked: honest`
- **THEN** 主 agent 告知用户该页被拦截、未取到正文；不解验证码；不把被挡页当正文

#### Scenario: collaborate 策略给协作路径
- **WHEN** fetch.py 返回 `blocked: needs_auth, on_blocked: collaborate`（如付费 paper PDF）
- **THEN** 主 agent 诚实说明 + 建议用户「浏览器登录后贴正文 / 给本地文件路径 / 提供 cookies」，不直接放弃

#### Scenario: 微信公众号经升级层抓取
- **WHEN** 用户要求读 `https://mp.weixin.qq.com/s?...` 且升级层已配置、执行端在线
- **THEN** 主 agent 经 `fetch.py --real-browser` 取到正文（`source: "universal-page-fetcher"`），不再告知「已知不支持」

#### Scenario: 带 warning 的结果向用户说明
- **WHEN** fetch.py 输出含 `warning: real_browser_unavailable_content_may_be_incomplete`
- **THEN** 主 agent 使用返回内容的同时，明确告知用户该页属于「普通抓取可能不完整」的站点且升级层当时不可用，内容可能有缺失

### Requirement: fetch.py 升级层开关默认关，按需显式开启
`fetch.py` SHALL 提供 `--real-browser` CLI 开关（默认关）。开关关闭时 MUST NOT 向 universal-page-fetcher 发任何请求，行为与无升级层时完全一致；开关开启且升级层可用时，才在域名直达或被挡升级两类场景使用它。任何调用方（主对话 web-page-fetch 入口、调研 subagent 等）SHALL 自行判断页面是否需要真实浏览器访问（需登录态 / 虚拟滚动长文档 / 被挡），需要即可带开关调用；批量抓取 SHOULD 只对确有需要的 URL 开启（执行端并发上限 10、单任务分钟级，整批盲目开启会把它打爆）。

**Lock**: user-confirmed
**Confirmed-At**: 2026-06-12

#### Scenario: 默认关——被挡不升级
- **WHEN** `fetch.py <url>`（无开关）抓到 anti_bot 被挡页
- **THEN** 直接返回 `{"blocked": "anti_bot", "on_blocked": <策略>}`，全程不请求 universal-page-fetcher

#### Scenario: 开启——被挡先升级
- **WHEN** `fetch.py --real-browser <url>` 抓到 needs_auth（HTTP 403），升级层已配置且执行端在线
- **THEN** 先经 universal-page-fetcher 抓取，成功则返回 `source: "universal-page-fetcher"`；失败才返回 blocked 输出

#### Scenario: 调研 subagent 按需升级
- **WHEN** evidence-search 的证据源中有一篇飞书文档需要完整正文
- **THEN** 可以对该 URL 带 `--real-browser` 调用 fetch.py 升级抓取；同批其余普通网页不带开关

### Requirement: 域名直达清单跳过普通链

`fetch.py` 在开关开启且升级层可用时，SHALL 对 host 命中「站点 → 抓取能力」清单中 `capability: real-browser` 条目的 URL 直接走 universal-page-fetcher，不先经直连 + Jina Reader。命中判定与清单格式见「站点 → 抓取能力清单的格式与 host 匹配」需求（清单 `site-fetch.txt` 默认含 feishu.cn / larksuite.com / notion.so / notion.site / yuque.com / mp.weixin.qq.com；匹配 = host 等于条目或以 `.<条目>` 结尾）。直达失败时 SHALL 回落普通链，且成功输出 MUST 附 `warning: "real_browser_unavailable_content_may_be_incomplete"`。

**Lock**: user-confirmed
**Confirmed-At**: 2026-06-14

#### Scenario: 飞书文档直达
- **WHEN** `fetch.py --real-browser https://xxx.feishu.cn/docx/yyy`，升级层可用
- **THEN** 不发直连与 Jina 请求，直接经 universal-page-fetcher 抓取并返回完整正文

#### Scenario: 直达失败回落普通链并带 warning
- **WHEN** 清单命中（capability=real-browser）的 URL 经 universal-page-fetcher 抓取失败（执行端离线 / 超时），回落普通链经 Jina 取到内容
- **THEN** 输出 `source: "jina-reader"` 且附 `warning: "real_browser_unavailable_content_may_be_incomplete"`

#### Scenario: 未命中清单的 URL 走普通链
- **WHEN** `fetch.py --real-browser https://example.com/article`（不在清单内）且页面正常
- **THEN** 走直连 + Jina Reader 普通链，不请求 universal-page-fetcher

### Requirement: coverage 残缺按失败处理
universal-page-fetcher 返回 `coverage.suspectIncomplete === true` 时，`fetch.py` SHALL 视该次升级抓取为失败（不把残缺内容当成功返回），走对应回落分支；`suspectIncomplete` 为 false 时 SHALL 透传 coverage 字段供调用方汇报抓取规模。

#### Scenario: suspectIncomplete 判失败
- **WHEN** 升级抓取返回 200 但 `coverage.suspectIncomplete: true`
- **THEN** 该结果不作为成功输出；按所在场景回落（直达 → 普通链 + warning；被挡升级 → blocked 输出）

### Requirement: 升级层连接配置沿用 universal-page-fetcher 自有约定
`fetch.py` SHALL 按以下优先级读取升级层连接配置：环境变量 `UNIVERSAL_PAGE_FETCHER_WORKER_URL` / `UNIVERSAL_PAGE_FETCHER_PASSWORD` → `~/.config/universal-page-fetcher/config.json`（`workerUrl` / `password` 字段）。两处都没有 = 升级层不可用，静默跳过（不报错、不提示配置）。本插件配置文件 MUST NOT 重复存储对方的地址与密码。密码值 MUST NOT 出现在 stdout / stderr / 异常文本中，鉴权失败只输出固定描述。

#### Scenario: 未配置时静默跳过
- **WHEN** `fetch.py --real-browser <url>`，环境变量与 config.json 均不存在
- **THEN** 行为与开关关闭时一致，无升级请求、无配置告警

#### Scenario: 鉴权失败不泄露密码
- **WHEN** 升级请求返回 HTTP 401
- **THEN** stderr 只含「鉴权失败，请核对 universal-page-fetcher 配置」类固定文案，不含 Authorization 头或密码值，且本进程内不再重试升级层

### Requirement: 站点 → 抓取能力清单的格式与 host 匹配

`fetch.py` 与拦截 hook SHALL 共用一份「站点 → 抓取能力」清单作为单一事实源，取代原 `direct_domains`。

- 格式：**行式纯文本**清单 `site-fetch.txt`，一行一条 `<域名>|<能力>`；`#` 起头或空行忽略；能力列可省，默认 `real-browser`。
- 选行式 txt 而非 YAML：一行一条最简、append 友好（`grep` 查站点 / `wc -l` 数条目 / `sort -u` 去重均可直接用），解析只需 `split('|')`，无需 YAML 解析器。
- `capability` 为**开放枚举**；本阶段仅 `real-browser` 有实装语义（`jina` / `raw` 由 fetch.py 按 Content-Type 自动判定、无需登记，其余值留作后续扩展，未实装分支 MUST NOT 改变行为）。
- host 匹配规则沿用既有约定：**host 等于条目，或以 `.<条目>` 结尾**。
- 加载与匹配逻辑 MUST 抽为共享函数（`lib/fetch_routing.py`），`fetch.py` 与 hook 同源调用，清单与规则不得各自维护。
- 清单位置：active `~/.config/search-crew/site-fetch.txt`；缺失 / 空 / 读失败 → `lib/fetch_routing` 内置默认（6 个已知「普通链成功但残缺 / 强风控」的站点，全 real-browser），功能不依赖文件存在。

**Lock**: user-confirmed
**Confirmed-At**: 2026-06-14

#### Scenario: 能力列可省，默认 real-browser
- **WHEN** 清单某行只写域名 `foo.com`（无 `|` 与能力列）
- **THEN** 解析为 `(foo.com, real-browser)`

#### Scenario: 注释与空行忽略
- **WHEN** 清单含 `#` 起头的注释行与空行
- **THEN** 解析时跳过，不产生条目

#### Scenario: 后缀匹配
- **WHEN** 查询 host `xxx.feishu.cn`，清单含条目 `feishu.cn`
- **THEN** 判定命中（以 `.feishu.cn` 结尾）

#### Scenario: fetch.py 与 hook 命中同一份清单
- **WHEN** 同一个 host（如 `mp.weixin.qq.com`）分别被 `fetch.py` 与拦截 hook 查询
- **THEN** 两者经同一共享函数得到相同的 capability 判定结果

#### Scenario: active 缺清单时用内置默认
- **WHEN** active `~/.config/search-crew/site-fetch.txt` 不存在
- **THEN** 用 `lib/fetch_routing` 内置默认 6 站点，微信等仍判 `real-browser`

### Requirement: PreToolUse hook 按清单分级拦截内置 WebFetch

plugin SHALL 自带一个 PreToolUse hook（matcher `WebFetch`，随 plugin 分发、用 `${CLAUDE_PLUGIN_ROOT}` 引脚本，MUST NOT 要求用户手改全局配置），按「站点 → 抓取能力」清单分级拦截内置 WebFetch 调用：

- host 命中清单且 `capability != builtin-webfetch` → **每次硬拦**（`permissionDecision: "deny"`），理由中 MUST 指明该站点应使用的能力与 `fetch.py --real-browser <url>` 命令。硬拦 MUST NOT 依赖 session 状态。
- 其余 host → **本 session 首次软拦**（`deny` + 提示优先 `fetch.py`、若已 WEBFETCH_FALLBACK 则重试本次），retry 后放行，为 `WEBFETCH_FALLBACK` 回落留逃生舱。
- hook MUST **fail-open**：`tool_input.url` 缺失 / 解析异常 / 自身错误时一律放行，绝不因 hook 故障阻断正常工具调用。
- 软拦的 session flag MUST 可在新 session / `/clear` / `/resume` / auto-compact 后复位（plugin 自带 SessionStart hook 清理）；硬拦不受此影响。

**Lock**: user-confirmed
**Confirmed-At**: 2026-06-14

#### Scenario: 微信链接每次硬拦
- **WHEN** 主 agent 对 `https://mp.weixin.qq.com/s/xxx` 发起内置 WebFetch（清单命中 capability=real-browser）
- **THEN** hook 返回 `deny`，理由指明该站点应跑 `fetch.py --real-browser`；同 session 再次发起仍硬拦

#### Scenario: 普通域名首次软拦、retry 放行
- **WHEN** 主 agent 对 `https://example.com/article`（不在清单）首次发起内置 WebFetch
- **THEN** hook 首次 `deny` 并提示优先 fetch.py；主 agent 重试同一调用时放行

#### Scenario: fetch.py 回落经软拦逃生
- **WHEN** `fetch.py example.com` 返回 `WEBFETCH_FALLBACK`，主 agent 据此回落内置 WebFetch
- **THEN** 该次 WebFetch 至多被软拦一次，retry 即放行，不形成死锁

#### Scenario: url 缺失时 fail-open
- **WHEN** hook 收到的 `tool_input` 不含可解析的 url
- **THEN** hook 放行该调用，不阻断

#### Scenario: compact 后软拦复位
- **WHEN** 同 session 经历 auto-compact 后，主 agent 再次对某非清单 URL 发起内置 WebFetch
- **THEN** 软拦首次拦截重新生效（SessionStart 已清旧 flag）


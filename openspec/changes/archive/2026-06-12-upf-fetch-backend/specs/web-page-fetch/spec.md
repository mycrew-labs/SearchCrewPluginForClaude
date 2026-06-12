# web-page-fetch Delta: upf-fetch-backend

## REMOVED Requirements

### Requirement: web-page-fetch 按 on_blocked 策略分派 + 已知不支持站点
**Reason**: 「微信公众号已知不支持」的承诺被 universal-page-fetcher（真实已登录浏览器执行端）推翻；「B-006 远程 browser-host 预留插入点」的表述随 OpenCLI 方案作废。分派行为本身保留，由下方 ADDED 的「web-page-fetch 分派与升级路径」需求接替并扩展。
**Migration**: 原 on_blocked 策略语义（honest / collaborate、不解验证码、不把被挡页当正文）全部并入新需求，无行为丢失；删除的只有「微信不支持」承诺与 OpenCLI 预留表述。
**原 Lock**: user-confirmed（2026-05-26）——本删除已于 2026-06-12 单独提请用户确认。

## ADDED Requirements

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
`fetch.py` 在开关开启且升级层可用时，SHALL 对 host 命中 `limits.yaml` `web_page_fetch.real_browser.direct_domains`（默认含 feishu.cn / larksuite.com / notion.so / notion.site / yuque.com / mp.weixin.qq.com；匹配 = host 等于条目或以 `.<条目>` 结尾）的 URL 直接走 universal-page-fetcher，不先经直连 + Jina Reader。直达失败时 SHALL 回落普通链，且成功输出 MUST 附 `warning: "real_browser_unavailable_content_may_be_incomplete"`。

**Lock**: user-confirmed
**Confirmed-At**: 2026-06-12

#### Scenario: 飞书文档直达
- **WHEN** `fetch.py --real-browser https://xxx.feishu.cn/docx/yyy`，升级层可用
- **THEN** 不发直连与 Jina 请求，直接经 universal-page-fetcher 抓取并返回完整正文

#### Scenario: 直达失败回落普通链并带 warning
- **WHEN** 直达清单命中的 URL 经 universal-page-fetcher 抓取失败（执行端离线 / 超时），回落普通链经 Jina 取到内容
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

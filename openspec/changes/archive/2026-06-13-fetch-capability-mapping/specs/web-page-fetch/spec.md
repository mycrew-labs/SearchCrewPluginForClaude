# web-page-fetch Specification（delta）

## ADDED Requirements

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

## MODIFIED Requirements

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

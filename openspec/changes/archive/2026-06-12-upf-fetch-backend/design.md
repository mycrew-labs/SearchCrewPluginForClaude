# Design: upf-fetch-backend

## Context

fetch.py 现有抓取链：直连 GET → 反爬/登录墙识别 → raw 直返或 Jina Reader 渲染 → 被挡时按 `on_blocked` 策略输出。链中已预埋一个远程升级层 `_try_remote_host()`（B-006 OpenCLI 方案的客户端，Basic auth + 单次 GET），但服务端从未实现，配置默认关闭，等于死代码。

universal-page-fetcher（下称「真实浏览器执行端」）已上线：Cloudflare Worker 网关 + 用户真实已登录 Chrome，契约为 Bearer 鉴权、`/fetch?url=` 轮询制（快任务直接 200；慢任务 202 + jobId 续等，间隔 2s，总时长上限 15 分钟）、`/health` 查执行端在线状态（`extensionOnline`）、返回 `{url, title, markdown, coverage}`，`coverage.suspectIncomplete=true` 表示可能没抓全、按约定当失败处理，结果只交付一次。

用户决策（2026-06-12）：web-page-fetch 是唯一入口与分派点；只有必要的页面才升级到真实浏览器执行端。

## Goals / Non-Goals

**Goals:**

- 把 fetch.py 的远程升级层换成 universal-page-fetcher 契约，覆盖两类「必要」场景：
  1. 已知 Jina「成功但残缺」的域名（虚拟滚动长文档、强风控站）——失败信号探测不到，必须靠清单直达；
  2. 运行时被挡（anti_bot / needs_auth）——失败信号触发升级。
- 升级行为默认关闭，调用方按需显式开启；批量抓取只对确有需要的 URL 开（防执行端过载）。
- 所有升级失败路径原样落回现有诚实兜底（on_blocked / WEBFETCH_FALLBACK）。

**Non-Goals:**

- 不合并两个仓库，不在本插件内置任何 universal-page-fetcher 的部署/构建产物。
- 不在本插件配置中存储对方的连接凭据（沿用其自有约定）。
- 不动 anti_bot / needs_auth 的识别逻辑（两条 locked 需求保持不变）。

## Decisions

### D1 开关形态：CLI 参数 `--real-browser`，默认关、按需显式开启

- 备选 a）环境变量：跨进程泄漏，subagent 继承后会**无意识**开启，否决。
- 备选 b）limits.yaml 全局开关：所有调用一刀切，表达不了「按 URL 判断必要性」，否决。
- 选定：`fetch.py --real-browser <url>`，调用方逐次显式声明。
- **调用方范围（2026-06-12 用户拍板修订）**：初稿曾限定「仅主对话 web-page-fetch 入口可用、调研 subagent 禁用」；用户裁定**所有调用方都可用**——页面需不需要真实浏览器访问，由各 agent 自行判断，需要即可带开关。对执行端的保护从「禁用」降为「批量只对确有需要的 URL 开启」的指引。
- 命名取「能力」而非产品名（升级到真实浏览器抓取），后端将来可替换而语义不变；产品名在 help 文本与输出 `source` 字段中体现。

### D2 配置分两处：连接归对方约定，策略归 limits.yaml

- 连接配置（地址 + 密码）按 universal-page-fetcher 自己的约定读取，优先级：环境变量 `UNIVERSAL_PAGE_FETCHER_WORKER_URL` / `UNIVERSAL_PAGE_FETCHER_PASSWORD` → `~/.config/universal-page-fetcher/config.json`（`{"workerUrl", "password"}`）。两处都没有 = 升级层不可用，静默跳过。不在 limits.yaml 重复存储，避免双源漂移。
- 分派策略进 `defaults/limits.yaml` 的 `web_page_fetch.real_browser` 段：
  - `direct_domains`：直达清单，默认 `feishu.cn / larksuite.com / notion.so / notion.site / yuque.com / mp.weixin.qq.com`；匹配规则为 host 等于条目或以 `.<条目>` 结尾。
  - `wait_sec`：单次抓取轮询总预算，默认 480（执行端单任务上限 15 分钟，但同步 CLI 不宜等满；SKILL.md 指引调用方给 Bash 设 10 分钟超时）。

### D3 轮询状态机与网络容错

首次 `GET /fetch?url=<encoded>`；200 → 直接取结果；202 → 解析 jobId 后每 2s `GET /fetch?job=<id>` 续等。已拿到 jobId 后的单次网络错误不判失败（任务仍在服务端跑），连续失败 10 次或总时长超 `wait_sec` 才放弃。401（密码错）/ 503（执行端离线）不重试。结果只交付一次，拿到即用。

升级层每进程首次使用前调一次 `/health`，`extensionOnline` 非 true 则本进程内标记不可用（缓存结果），避免批量时反复探测或向离线执行端排队投任务。

HTTP 一律走 `lib/_http`（统一打点、豁免站点调用上限）；轮询需要读 status code，现有 helper 不暴露则在 `lib/_http` 加一个返回 `(status, body)` 的薄函数，不绕开打点。

### D4 分派顺序（`_fetch_one` 内）

```
开关开 且 域名命中 direct_domains 且 升级层可用
  → 先走真实浏览器执行端；成功即返回
  → 失败则继续普通链，但输出附 warning 字段（见 D6）
普通链：直连 → 识别被挡/raw/HTML（不变）
  被挡（anti_bot / needs_auth）：开关开且可用 → 试真实浏览器执行端；
    成功 → 返回；失败 → 按现状输出 blocked + on_blocked
  Jina 失败 / Jina 结果被挡：同上，失败落 WEBFETCH_FALLBACK / blocked（同现状）
```

### D5 成功输出形态

`{"source": "universal-page-fetcher", "url", "title", "markdown", "coverage": {...}, "fallback": null}`。`coverage.suspectIncomplete=true` **不算成功**——视为升级失败走对应回落分支；其余 coverage 字段透传，供 skill 向用户汇报抓取规模。

### D6 直达域名升级失败的诚实信号

直达清单存在的前提是「普通链会成功但残缺、且程序探测不到」。因此直达失败后回落普通链拿到的内容要带 `"warning": "real_browser_unavailable_content_may_be_incomplete"`，SKILL.md 指引主 agent 据此向用户说明内容可能不完整。不带 warning 静默返回会违背「要么抓全，要么明确告知」的循证原则。

### D7 移除 OpenCLI 残留

删除 `_try_remote_host()`、limits.yaml 的 `remote_host` 段及相关注释（含 fetch.py docstring、limits.yaml 里的 B-006 表述）。理由：服务端从未存在、默认关闭，保留两套远程层只会混淆。`openspec/project.md` B-006 条目改记「已被 universal-page-fetcher 取代」，原调研笔记保留。

### D8 密码红线

Authorization 头的值不得出现在 stdout / stderr / 异常文本中；报错只说「鉴权失败（401），请核对配置」。沿用全局 Secrets 规则。

## Risks / Trade-offs

- [执行端并发上限 10，批量误投会排队拖慢] → 开关默认关 + 按需逐 URL 开启的指引（agent / skill 文档明示「别整批盲目开」）；批量模式下命中直达清单的 URL 仍逐个走升级层，但受 fetch.py 并发 5 限制，低于上限。
- [轮询最长 480s，Bash 工具默认超时 120s 会拦腰截断] → SKILL.md 明确指引：带 `--real-browser` 的调用设 timeout 600000ms；脚本侧 `wait_sec` 留余量（480s < 600s）。
- [结果只交付一次，超时被截断后结果丢失] → 截断后重发即重新抓取，成本可接受；不做结果缓存（如无必要勿增实体）。
- [直达清单是硬编码站点知识，会过时] → 清单放用户态 limits.yaml 可改；默认值只收录有明确证据（universal-page-fetcher 实测攻克）的站点。
- [微信等站点执行端也可能失败（登录态过期等）] → 失败落回 anti_bot + on_blocked，与现状等同，无回退风险。

## Migration Plan

无线上服务，合并即生效。`remote_host` 配置段移除属低风险 BREAKING：默认关闭且服务端从未存在；用户态 limits.yaml 若残留该段，读取方直接忽略未知键，不报错。

## Open Questions

（无——批量路径是否未来开放升级、图片/附件随包等归 universal-page-fetcher 自己的 Roadmap 与本仓库后续 change。）

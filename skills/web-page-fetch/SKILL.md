---
name: web-page-fetch
description: 拿到具体 URL 要读取 / 总结 / 抽取其网页或文件内容时，MUST 用本 skill，不要直接用内置 WebFetch。覆盖普通网页、raw 文件（GitHub raw 的 README/.md/.json/源码）、需登录态页面，以及微信公众号 / 飞书 / Lark / Notion / 语雀这类反爬或虚拟滚动长文档（自动升级真实浏览器抓取）。仅当本 skill 返回 WEBFETCH_FALLBACK 时才回落内置 WebFetch。不要用于没有具体 URL 的普通搜索 / 跨站调研（那是 evidence-search / site-search / deep-search）。
---

# web-page-fetch

读一个**具体 URL** 的内容时，主 agent 优先用这个能力，而不是直接用内置 WebFetch。

> **fetch backend 是当前实现，不是身份**。当前实现是「直连探测 + Jina Reader 渲染 + 必要时升级 universal-page-fetcher（真实已登录浏览器执行端）」。本 skill 的契约（输入 URL、三态输出、不把反爬页当正文）保持不变。

## 何时用

- 用户给出具体 URL，要读取 / 总结 / 抽取页面或文件内容
- 需要读 raw 文件（`raw.githubusercontent.com` 的 README、`.md` / `.json` / 源码等）
- 需登录态的页面、飞书 / Notion / 语雀等虚拟滚动长文档、微信公众号文章——本 skill 会自动升级到真实浏览器抓取，**不要**为这些场景另寻工具

## 何时**不**用

- 普通搜索 / 找资料 / 跨站调研 → evidence-search / site-search / deep-search
- 没有具体 URL，只有关键词 → 先搜

## 用法

```bash
python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/fetch.py --real-browser <url>
```

主对话入口固定带 `--real-browser`，并给 Bash 工具设 timeout 600000ms——升级抓取走真实浏览器滚动遍历，慢页可达分钟级。`fetch.py` 自动判 HTML（Jina Reader 渲染）/ raw（原文直取），识别反爬墙，并在两类「必要」场景升级到 universal-page-fetcher：

1. **域名直达**：host 命中 site-fetch 清单（`site-fetch.txt` 中 capability=real-browser 的条目，与「读 URL 拦截 hook」共用，见 `scripts/lib/fetch_routing.py`）→ 跳过普通链直接走真实浏览器。默认清单及收录理由：
   - `feishu.cn` / `larksuite.com` / `notion.so` / `notion.site` / `yuque.com`：**虚拟滚动长文档**——正文随滚动按需渲染，Jina 等服务端抓取只能拿到首屏附近的内容，且返回的是「成功但残缺」，程序无法从失败信号探测到；真实浏览器执行端会自动滚动遍历到底再抽取。
   - `mp.weixin.qq.com`：**风控 + 滑块验证码墙**——服务端无头抓取必撞验证页；真实浏览器带设备原生指纹与登录态，可正常取文。
2. **被挡升级**：撞上验证码墙 / 登录付费墙 / 抓取链失败 → 先试真实浏览器，仍失败才按 blocked 输出。

升级层未配置（环境变量 `UNIVERSAL_PAGE_FETCHER_WORKER_URL` / `UNIVERSAL_PAGE_FETCHER_PASSWORD` 或 `~/.config/universal-page-fetcher/config.json`，详见其[项目 README](https://github.com/mycrew-labs/universal-page-fetcher)）或执行端离线时静默跳过，行为同纯 Jina 链。读取操作豁免站点调用上限，可放心抓多个 URL。

> `--real-browser` 对所有调用方开放（调研 subagent 也可用）：页面需不需要真实浏览器访问，由调用方自行判断，需要即可带。唯一克制点：批量抓取只对确有需要的 URL 开启——执行端并发上限 10、单任务分钟级，整批盲目开启会把它打爆。

## 按输出分派

| 输出 | 含义 | 怎么办 |
|---|---|---|
| `source: "jina-reader"` / `"raw"` / `"universal-page-fetcher"` | 成功 | 用返回的 `markdown`；带 `coverage` 时可向用户汇报抓取规模（滚动屏数、字符数） |
| 成功输出额外带 `warning: "real_browser_unavailable_content_may_be_incomplete"` | 该站点普通抓取可能不完整，且升级层当时不可用 | 内容可用，但 MUST 向用户说明「升级抓取暂不可用，内容可能有缺失」 |
| `fallback: "WEBFETCH_FALLBACK"` | 无 key / 网络失败 | 改用内置 WebFetch |
| `blocked: "anti_bot"` | 验证码 / 风控墙（升级层也没拿到） | 见下方「被挡怎么办」；MUST NOT 解验证码、MUST NOT 把验证页当正文 |
| `blocked: "needs_auth"` | 登录墙 / 付费墙（401/403，升级层也没拿到） | 见下方「被挡怎么办」 |

### 被挡怎么办（看输出里的 `on_blocked` 策略）

走到 blocked 输出，意味着升级层也试过了（或未配置）。`fetch.py` 会带上用户配置的 `on_blocked`（来自 `limits.yaml`）：

- **`on_blocked: "honest"`（默认）**：诚实告知用户「该页被 <反爬墙 / 登录墙> 拦截，未取到正文」，不打断流程，不强求用户做事。升级层未配置时可顺带提一句：配好 universal-page-fetcher 后这类页面多数能抓。
- **`on_blocked: "collaborate"`**：诚实说明 + 主动给用户协作路径（按 blocked 类型挑合适的）：
    - `needs_auth`（登录/付费，如付费 paper PDF）：建议「你用账号在浏览器打开后把正文贴给我」/「下载到本地，给我文件路径，我读本地」/「提供 cookies」
    - `anti_bot`（验证码）：建议「你浏览器打开过验证后把正文贴给我」
    - 用户不愿配合 / 拿不到 → 才放弃

## 与内置 WebFetch 的关系

读 URL 优先本 skill 由**两层**保障：

1. **description 触发层**（软）：本 skill 描述引导主 agent 优先走 fetch.py——但它打不过内置 WebFetch 的注意力优势，可能漏触发。
2. **PreToolUse hook 动作点兜底**（`hooks/webfetch_gate.py`，随 plugin 分发）：主 agent 真去调内置 WebFetch 时拦截——site-fetch 清单命中的站点（微信等）**每次硬拦**并指明改用 `fetch.py --real-browser`；其余站点**本 session 首次软拦、retry 放行**（给 `WEBFETCH_FALLBACK` 回落留路）。

只在 `fetch.py` 给 `WEBFETCH_FALLBACK`（无 key / 网络失败）时才回落内置 WebFetch。相比内置 WebFetch，本路径：Jina Reader 渲染 JS、产出更干净 markdown、raw 文件原文保真、有反爬识别、能升级真实浏览器拿登录态与虚拟滚动长文档、走 usage 打点。

> 历史订正：早期文档曾称「Claude Code 无法拦截内置工具、只能软引导」——这已不成立。PreToolUse hook 可拦截内置 WebFetch，故有上面第 2 层。

---
name: web-page-fetch
description: 读取 / 总结 / 抽取一个具体 URL 的网页或文件内容时使用。优先用本 skill（走 fetch.py：Jina Reader 渲染 HTML + raw 文件原文直取 + 反爬识别 + usage 打点）而非内置 WebFetch；仅在它返回 WEBFETCH_FALLBACK 时才回落内置 WebFetch。不要因普通搜索 / 跨站调研触发（那是 fast-search / site-search / deep-search 的活）。
---

# web-page-fetch

读一个**具体 URL** 的内容时，主 agent 优先用这个能力，而不是直接用内置 WebFetch。

> **fetch backend 是当前实现，不是身份**。当前实现是「直连探测 + Jina Reader 渲染」；未来可接入更多源类型 / 解析器（如 [B-006 OpenCLI 浏览器后端](../../openspec/project.md)）。本 skill 的契约（输入 URL、三态输出、不把反爬页当正文）保持不变。

## 何时用

- 用户给出具体 URL，要读取 / 总结 / 抽取页面或文件内容
- 需要读 raw 文件（`raw.githubusercontent.com` 的 README、`.md` / `.json` / 源码等）

## 何时**不**用

- 普通搜索 / 找资料 / 跨站调研 → fast-search / site-search / deep-search
- 没有具体 URL，只有关键词 → 先搜

## 用法

```bash
python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/fetch.py <url>
```

`fetch.py` 自动判 HTML（Jina Reader 渲染）/ raw（原文直取），并识别反爬墙。读取操作豁免站点调用上限，可放心抓多个 URL。

## 按输出分派

| 输出 | 含义 | 怎么办 |
|---|---|---|
| `source: "jina-reader"` 或 `"raw"` | 成功 | 用返回的 `markdown` |
| `fallback: "WEBFETCH_FALLBACK"` | 无 key / 网络失败 | 改用内置 WebFetch |
| `blocked: "anti_bot"` | 撞验证码 / 风控墙 | 见下方「被挡怎么办」；MUST NOT 解验证码、MUST NOT 把验证页当正文 |
| `blocked: "needs_auth"` | 登录墙 / 付费墙（401/403） | 见下方「被挡怎么办」 |

### 被挡怎么办（看输出里的 `on_blocked` 策略）

`fetch.py` 会在 blocked 输出里带上用户配置的 `on_blocked`（来自 `limits.yaml`）：

- **`on_blocked: "honest"`（默认）**：诚实告知用户「该页被 <反爬墙 / 登录墙> 拦截，未取到正文」，不打断流程，不强求用户做事。
- **`on_blocked: "collaborate"`**：诚实说明 + 主动给用户协作路径（按 blocked 类型挑合适的）：
    - `needs_auth`（登录/付费，如付费 paper PDF）：建议「你用账号在浏览器打开后把正文贴给我」/「下载到本地，给我文件路径，我读本地」/「提供 cookies」
    - `anti_bot`（验证码，如微信）：只能「你浏览器打开过验证后把正文贴给我」——别的路子堵死
    - 用户不愿配合 / 拿不到 → 才放弃

> **未来（[B-006](../../openspec/project.md)）**：`needs_auth` 会先自动走远程 browser-host（用登录态会话拿），仍拿不到才落到上面的 `on_blocked` 策略。当前版本没有这一跳。

## 已知不支持

- **微信公众号**（`mp.weixin.qq.com`）：风控 + 滑块验证码，Jina 和真实浏览器都过不去。直接告知用户不可抓，别反复试。
- 非验证码的 SPA / 需登录态页面：可建议升级到 `browser-control`（Chrome DevTools MCP）；但**验证码墙**浏览器也救不了。

## 与内置 WebFetch 的关系

本 skill 是**优先选择**，不是物理禁用 WebFetch（Claude Code 无法拦截内置工具）。只在 `fetch.py` 给 `WEBFETCH_FALLBACK` 时回落内置 WebFetch。相比内置 WebFetch，本路径：Jina Reader 能渲染 JS、产出更干净 markdown、raw 文件原文保真、有反爬识别、走 usage 打点。

# Proposal: upf-fetch-backend

## Why

[universal-page-fetcher](https://github.com/icedfish/universal-page-fetcher)（真实已登录浏览器 + Cloudflare Worker 网关的抓取执行端）已成熟并完成端到端验证，它正是 Backlog B-006 设想的「远程 browser-host」角色的更好实现——还攻克了 B-006 当时判定无解的微信公众号与虚拟滚动长文档（飞书 / Notion / 语雀）。用户已拍板（2026-06-12）：两仓库不合并；universal-page-fetcher 的独立调用方 skill 不再装在本机，**web-page-fetch 成为唯一入口与分派点**，只有必要的页面才升级到 universal-page-fetcher 抓取。

## What Changes

- `fetch.py` 的远程升级层从「OpenCLI browser-host（从未有过服务端实现）」**替换**为 universal-page-fetcher Worker 网关：Bearer 鉴权、`/fetch?url=` 轮询制（202 + jobId 续等）、`coverage.suspectIncomplete=true` 按失败处理。
- 新增**域名直达清单**：已知 Jina Reader「成功但残缺」的站点（飞书 / Notion / 语雀 / 微信公众号等虚拟滚动或强风控页）直接走 universal-page-fetcher，不浪费一次直连 + Jina；清单进 `defaults/limits.yaml`，用户可改。
- 升级行为由 **CLI 开关控制，默认关、按需显式开启**：任何调用方（主对话入口、调研 subagent）自行判断页面是否需要真实浏览器访问，需要即带 `--real-browser`；批量抓取只对确有需要的 URL 开，防止打爆执行端（并发上限 10、单任务分钟级）。（2026-06-12 用户拍板：放开初稿「仅主入口可用」的限制。）
- universal-page-fetcher 的连接配置沿用其自有约定（环境变量 `UNIVERSAL_PAGE_FETCHER_WORKER_URL` / `UNIVERSAL_PAGE_FETCHER_PASSWORD`，或 `~/.config/universal-page-fetcher/config.json`），**不在本插件配置中重复存储**；密码值不得进入任何输出。
- 升级失败（未配置 / 执行端离线 / 超时 / coverage 残缺）→ 原样落回现有 `on_blocked` 策略（honest / collaborate）与 `WEBFETCH_FALLBACK` 链路，诚实兜底不删。
- `web-page-fetch` SKILL.md：删除「微信公众号已知不支持」承诺（改为经 universal-page-fetcher 可抓），描述新分派行为与开关用法。
- **BREAKING（低风险）**：移除 `limits.yaml` 的 `web_page_fetch.remote_host` 配置段与 fetch.py 的 OpenCLI 客户端代码。该层默认关闭且服务端从未存在，无真实用户受影响。
- 更新 `openspec/project.md` Backlog B-006：OpenCLI 方案标记为已被 universal-page-fetcher 取代，调研笔记留作历史记录。

## Capabilities

### New Capabilities

（无——全部落在既有 web-page-fetch 能力内）

### Modified Capabilities

- `web-page-fetch`：
  - 「按 on_blocked 策略分派 + 已知不支持站点」（**Lock: user-confirmed**，改动需用户单独确认）：删除微信不支持承诺；blocked 时先尝试 universal-page-fetcher 升级，仍失败才落 on_blocked 策略。
  - 新增需求：域名直达清单、开关默认关、coverage 残缺判失败、连接配置沿用对方约定。
  - 「识别被挡页」「Content-Type 区分」两条 locked 需求**不变**（识别逻辑不动，只改识别之后的去向）。

## Impact

- 代码：`skills/search-toolkit/scripts/fetch.py`（替换远程层 + 域名直达 + 开关参数）
- 配置：`defaults/limits.yaml`（删 `remote_host` 段，增域名清单与等待时长）
- 文档：`skills/web-page-fetch/SKILL.md`、`openspec/project.md`（B-006）、README 若提及微信不支持则同步
- 测试：`tests/` 中 fetch 相关用例需覆盖新分派分支
- 仓库外（不在本 change 实施，仅记录）：用户本机 `~/.claude/skills/universal-page-fetcher/` 独立 skill 待用户自行卸载；universal-page-fetcher 仓库的调用方 skill 保留并加一句「与 SearchCrew 同用时入口统一走 web-page-fetch」

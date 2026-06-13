# Proposal: fetch-capability-mapping

## Why

主 agent 读 URL 时本应优先走 web-page-fetch（`fetch.py`），但触发**完全依赖模型自主判断**——与内置 WebFetch（一等公民工具，schema 常驻系统提示最显著位置）竞争注意力时经常落败。后果实例：微信公众号这类「内置 WebFetch 必然抓不到（强风控验证墙）」的页面被直接喂给 WebFetch，撞验证页、把反爬页当正文返回垃圾（2026-06-14 实测复现）。

根因有二，本 change 一并解决：

1. **缺动作点兜底**：插件只有 SKILL.md 的 description 在软引导，没有任何 hook 在「模型实际调内置 WebFetch」那一刻拦截。（SKILL.md 正文还残留一句过时认知——「Claude Code 无法拦截内置工具」——已被 PreToolUse hook 可 matcher 内置工具的事实推翻。）
2. **「站点 → 该用哪个抓取能力」只有退化形态**：现在仅有 `direct_domains` 单值清单（值域只有「真实浏览器」一种），无法表达「这个站该用 jina / raw / 站点适配器 / 内置 webfetch」，hook 拦截时也无从「告诉模型该改用哪个」。

## What Changes

按「每阶段消除一项不确定性」分两阶段交付。

**地基（阶段一）——把单值清单升级成一份行式清单：**
- 将 `direct_domains` 升级为一份**「站点 → 抓取能力」行式纯文本清单** `site-fetch.txt`（一行 `<域名>|<能力>`，`grep` / `wc` / `sort -u` 友好、append 友好）：能力当前实装 `real-browser`，现有域名平滑迁移，行为不回退。
- `fetch.py` 与新 hook **共用这份清单**：读清单与 host 匹配抽成共享函数（`lib/fetch_routing`），单一事实源，永不漂移。

**第一层（提示词，降低漏触发率）：**
- 精简强化 SKILL.md frontmatter `description`：触发判据 + 排他指令（不要直接用内置 WebFetch）前置，实现细节移入正文。
- 修正正文过时认知，「与内置 WebFetch 的关系」节改写为「description + hook 双层」模型。

**第二层（hook 动作点兜底）：**
- 新增 plugin 自带 PreToolUse hook（matcher `WebFetch`），按 mapping **分级拦截**：
  - mapping 指定「非内置 WebFetch 能力」的站点（如微信 → real-browser）→ **每次硬拦**（`deny`），reason 明确指出该用哪个能力 / 跑 `fetch.py --real-browser`。无逃生舱：这些站点 fetch.py 不会回落 WebFetch，内置 WebFetch 对它们本就无效。
  - 其余站点 → **session 首次软拦 + retry 放行**，给 fetch.py 的 `WEBFETCH_FALLBACK` 回落留逃生舱。
- hook 用 Python，复用上面的共享 mapping 函数。
- 配套（软兜底）plugin 自带 SessionStart hook 清自己的 session flag，保证 compact / clear 后软拦重新生效；硬拦不依赖 flag，不受影响。

**生长（阶段二）——让 mapping 随使用沉淀：**
- mapping 接入既有「用户态 active + pending/promote + changelog」机制（对应 Backlog 自我进化）：AI 想到新站点规则写 `pending/`，用户「晋升」才合并。`MUST` 遵守 `config-lifecycle` 既有 locked 规则，不另立写入路径。

## Capabilities

### New Capabilities

（无——全部落在既有能力内）

### Modified Capabilities

- `web-page-fetch`：
  - 「域名直达清单跳过普通链」（**Lock: user-confirmed**，改动需用户单独确认）：从单值 `direct_domains` 泛化为「站点 → 抓取能力 mapping」，`direct_domains` 成为退化特例。
  - 「主 agent 读 URL 优先用 web-page-fetch，零 key 才回落内置 WebFetch」（ai-derived）：补强为「description 触发层 + PreToolUse hook 动作点兜底」双层，新增 hook 分级拦截行为。
  - 新增需求：站点 → 能力 mapping 数据结构与 host 匹配规则；hook 按 mapping 分级拦截（硬拦 / 软拦）。
  - 「Content-Type 区分」「识别被挡页判失败」「升级层开关默认关」「升级层连接配置沿用对方约定」等 locked 需求**不变**。
- `orchestration`：
  - 「主 agent 读 URL 优先用 web-page-fetch skill」（ai-derived）：与上同步，从「软优先」明确为「双层保障」。
- `config-lifecycle`（仅**阶段二**触及，多条 **Lock: user-confirmed**）：mapping 的 active 化与 pending/promote 生长 `MUST` 遵守既有「仅经固定脚本写 active」「pending 晋升经 promote」「changelog 留痕」locked 规则；**阶段一只在 `defaults/` 内新增数据结构、不改 config-lifecycle 行为**。

## Impact

- 代码：新增 `skills/search-toolkit/scripts/lib/fetch_routing.py`（读 txt 清单 + host 匹配）、`fetch.py` 改用之、新增 `hooks/webfetch_gate.py` + `hooks/session_reset.py`（Python）。
- 插件清单：新增 `hooks/hooks.json`（注册 PreToolUse matcher `WebFetch` + SessionStart，`${CLAUDE_PLUGIN_ROOT}` 引脚本）。
- 配置：新增 `defaults/site-fetch.txt`（行式站点清单）；`defaults/limits.yaml` 移除 `direct_domains`、`real_browser` 段只留 `wait_sec`。
- 文档：`skills/web-page-fetch/SKILL.md`（description + 正文双层改写）、README（若提及读 URL 触发方式则同步）。
- 测试：`tests/` 覆盖 mapping 加载/匹配、hook 硬拦/软拦/retry 放行/fallback 逃生分支。
- 分发：hook 随 plugin 走，所有安装者自动获得，不要求用户手改全局配置。

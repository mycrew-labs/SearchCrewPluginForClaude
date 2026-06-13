# Design: fetch-capability-mapping

## Context

读 URL 的现状链路：`web-page-fetch` skill 的 SKILL.md `description` 软引导主 agent 调 `fetch.py`，主 agent 自主决定是否采纳。与内置 WebFetch（一等公民工具，schema 常驻系统提示最显著处）竞争注意力时经常落败——2026-06-14 实测：给微信公众号 URL，主 agent 直接调内置 WebFetch、撞验证墙、险些把反爬页当正文。

两处文档还固化了一个**过时认知**：SKILL.md 正文「Claude Code 无法拦截内置工具」、orchestration spec「此偏好为软引导（Claude Code 无法物理禁用内置 WebFetch）」。经核实（Claude Code 官方 hooks 文档 + 实测），PreToolUse hook 可 `matcher: "WebFetch"` 并以 `permissionDecision: "deny"` 拦截内置工具——软引导可以升级为「软引导 + 动作点兜底」双层。

「站点 → 该用哪个能力抓」当前只有退化形态：`limits.yaml` 的 `web_page_fetch.real_browser.direct_domains` 是个单值清单（命中 = 走真实浏览器），值域只有一种，无法表达更丰富的「这个站用哪个能力」，hook 拦截时也无从「告诉模型改用哪个」。

## Goals / Non-Goals

**Goals:**

- 主 agent 漏走 fetch.py、直接调内置 WebFetch 时，有动作点兜底把它纠回正确能力。
- 把 `direct_domains` 升级为可扩展的「站点 → 抓取能力」mapping，`fetch.py` 与 hook **共用同一份事实源**。
- 纠正 SKILL.md 与 orchestration spec 里「无法拦内置工具」的过时认知。
- 分两阶段交付，阶段一立地基 + 解决微信类痛点。

**Non-Goals:**

- 阶段一**不实装没有真实消费者的能力值**（只实装 `real-browser`）；不引入「白名单」（明确放行内置 WebFetch 的站点）。
- 不改 anti_bot / needs_auth 识别、Content-Type 区分、升级层开关默认关等既有 **locked** 行为（只改「识别 / 选择之后的去向」与「单值 → mapping」的数据结构）。
- 阶段二的 active 化 + pending/promote 生长不在阶段一。

## Decisions

### D1 双层防线：description（软）+ PreToolUse hook（动作点兜底）

- 第一层 `description`：精简强化、排他指令前置，降低漏触发率——但它本质是软的，打不过一等公民的注意力优势，单靠它不可靠。
- 第二层 PreToolUse hook（matcher `WebFetch`）：在主 agent **实际调内置 WebFetch 的那一刻**拦截。这是唯一能可靠纠偏的官方手段（无 frontmatter 字段能强制模型优先用 skill）。
- 两层各司其职：description 提升自主命中、降低 hook 触发频率；hook 保证漏了也能纠回。同步删除两处文档的「无法拦内置工具」过时表述。

### D2 mapping 配置 = 行式纯文本清单（site-fetch.txt），阶段一只实装 `real-browser`

- 形态（独立文件 `defaults/site-fetch.txt`，随 defaults 整目录 seed 到 active）：

  ```
  # 一行一条：<域名>|<能力>；# 注释与空行忽略；能力列可省，默认 real-browser
  mp.weixin.qq.com|real-browser
  feishu.cn|real-browser
  larksuite.com|real-browser
  notion.so|real-browser
  notion.site|real-browser
  yuque.com|real-browser
  ```

- 为什么行式 txt 而非 YAML：一行一条最简、append 友好（契合「逐渐形成的按站点历史」——pending 追加一行即可），且 `grep` 查站点、`wc -l` 数条目、`sort -u` 去重都能直接用；解析只需 `split('|')`，**无需 YAML 解析器**（初版的 YAML `site_capability` 结构是过度设计，已弃用）。
- `capability` 是开放枚举：阶段一只有 `real-browser` 有实装语义。`jina` / `raw` 是 fetch.py 按 Content-Type 自动判的默认、不需按站点指定；`builtin-webfetch` / `site-adapter` 暂无消费者，留作扩展，**不实现无消费者的分支**。
- 配置从 `limits.yaml` 抽出独立成文件：`limits.yaml` 的 `real_browser` 段只留 `wait_sec`，站点清单归 `site-fetch.txt`，职责清晰。
- 缺失兜底：active 无 `site-fetch.txt` 时用 `lib/fetch_routing` 内置默认（同上 6 站点），功能不依赖文件存在。

### D3 hook 分级拦截

- host 命中 mapping 且 `capability != builtin-webfetch` → **每次硬拦**（`deny`），reason 明确：「该站点指定用 `<capability>` 抓取，内置 WebFetch 对它无效；MUST 跑 `fetch.py --real-browser <url>`」。不依赖 session flag。
  - 无逃生舱的依据：这些站点 fetch.py **不会**回落内置 WebFetch（anti_bot 按 locked 识别需求明确「MUST NOT 走 WEBFETCH_FALLBACK」），内置 WebFetch 对它们本就必失败，没有合法的 WebFetch 路径可放行。
- 其余 host（不在 mapping 内）→ **session 首次软拦**：`deny` + 提示「读 URL 优先 `fetch.py`；若 fetch.py 已返回 WEBFETCH_FALLBACK 让你回落，请重试本次 WebFetch」，retry 放行。
  - retry 放行即 `WEBFETCH_FALLBACK` 的逃生舱：fetch.py 无 key / 网络失败回落 WebFetch 时，被拦一次重试即过，最坏多一次往返、不死锁。

### D4 单一事实源：host 匹配与清单加载抽共享函数

- 把「读 site-fetch.txt 清单 + host 匹配（host 等于条目或以 `.<条目>` 结尾）」抽到 `lib/fetch_routing.py`，`fetch.py` 与 hook 脚本共用（hook 加一行 `sys.path` 即可 import）。清单与匹配规则只在一处定义，永不漂移。
- 匹配规则沿用现有 locked 行为（host 等于条目或 `.<条目>` 后缀），不发明新规则。

### D5 hook 用 Python，随 plugin 分发

- hook 脚本用 Python（复用 D4 的 lib 与 plugin 自带 yaml 解析），不在 shell 手搓 yaml。
- 注册在 plugin 自带的 `hooks/hooks.json`，`command` 用 `"${CLAUDE_PLUGIN_ROOT}"/...` 引脚本。所有安装者自动获得，不要求用户手改全局配置（也不触碰 `~/.claude/`）。

### D6 session flag 与 compact 自愈

- 软拦的「本 session 首次」flag 落 `/tmp`。plugin 自带一个 SessionStart hook 清自己的 flag，保证 `/clear` / `/resume` / auto-compact 后软拦重新生效（compact 后 AI 上下文已重置，本应重新拦一次）。
- 硬拦**不依赖 flag**，compact 不影响关键路径——这是分级设计的额外红利：最重要的拦截天然 compact-safe。

### D7 阶段边界

- **阶段一**：D1–D6——`defaults/limits.yaml` 内 `direct_domains → site_capability`（含兼容读）、共享 lib、PreToolUse + SessionStart hook、SKILL.md description + 正文双层改写、orchestration spec 纠正过时表述。覆盖微信类痛点。
- **阶段二**：mapping 接入 `config-lifecycle` 既有「用户态 active + pending/promote + changelog」机制——AI 想到新站点规则写 `pending/`，用户「晋升」才经 `promote` 脚本合并。`MUST` 遵守那些 locked 规则，不另立写入路径。单独成阶段，不把「自动学习沉淀」的复杂度压进阶段一。

## Risks / Trade-offs

- [硬拦误伤合法 WebFetch] → 硬拦只作用于 `capability=real-browser` 的站点，这些站点 fetch.py 必不回落 WebFetch、内置 WebFetch 必失败，不存在合法放行路径；非 mapping 站点走软拦保留 retry 逃生。
- [compact 后软拦 flag 残留致失灵] → plugin SessionStart 清 flag；且硬拦不依赖 flag。
- [mapping 能力值虚胖、过度设计] → 阶段一只实装 `real-browser`，其余值留 schema 预留 + 文档示例。
- [老用户升级后 active 无 site-fetch.txt] → `lib/fetch_routing` 内置默认兜底，功能正常；新用户整目录 seed 自动获得该文件。老用户想在 active 编辑清单需手动 `cp`（seed `--merge` 只补 YAML 顶层段、不拷新文件），此便利缺口留文档说明 / 阶段二处理，不在阶段一改 seed（避免触及 config-lifecycle locked 的 seed 行为）。
- [hook 进程启动开销] → WebFetch 非高频调用，Python 启动 ~数十 ms 可接受。
- [hook 误判 tool_input 结构 / 非 WebFetch 调用] → hook 只读 `tool_input.url`，缺失或非 URL 时放行（fail-open），绝不因 hook 自身异常阻断正常工具调用。

## Migration Plan

- 配置：`defaults/limits.yaml` 移除 `direct_domains`，站点清单迁到独立 `defaults/site-fetch.txt`，`real_browser` 段只留 `wait_sec`。无线上服务，合并即生效。新用户整目录 seed 自动含 txt；老用户靠内置默认兜底。
- hook 随 plugin 分发，安装 / 升级后自动注册；卸载 plugin 即移除，不留全局残留。
- 回滚：移除 hooks.json 注册即回到「纯 description 软引导」，无数据迁移负担。

## Open Questions

- 能力值未来扩展（`builtin-webfetch` 白名单、`site-adapter` 直连站点适配器）按出现真实需求时起后续 change，不在本 change 预实现。
- 阶段二 pending/promote 的 mapping 晋升交互细节，留阶段二 design 展开。

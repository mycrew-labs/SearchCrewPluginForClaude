# Tasks: fetch-capability-mapping

> 本 change 实施**阶段一**（mapping 地基 + 双消费 + hook + 提示词双层）。阶段二（mapping 接入
> active + pending/promote 生长）见末节，另起 change。

## 1. 共享路由 lib（单一事实源）

- [x] 1.1 新增 `lib/fetch_routing.py`：读行式 txt 清单（`<域名>|<能力>`，`#`/空行忽略、能力列可省默认 real-browser），提供 `capability_for_host/url`（匹配：host 等于条目或以 `.<条目>` 结尾）+ `active_mapping()`（自算 active 路径）+ 内置默认
- [x] 1.2 `tests/test_fetch_routing.py`：解析 / 后缀匹配 / 防误前缀 / 能力列可省 / 空文件回落默认 / defaults 清单解析

## 2. fetch.py 接共享 lib（行为不回退）

- [x] 2.1 `fetch.py` 改用 `fetch_routing.active_mapping()` 判定 real-browser 直达，`_real_browser_cfg` 收敛为 `_rb_wait_sec`、删内联 `_DEFAULT_DIRECT_DOMAINS`
- [x] 2.2 现有直达行为不变：命中 real-browser → 升级层；失败回落普通链 + `warning`
- [x] 2.3 回归：`tests/test_fetch.py` 全过（含 direct_domain / 升级 / 回落分支）

## 3. 配置数据结构迁移

- [x] 3.1 新增 `defaults/site-fetch.txt`（行式清单，6 站点）；`defaults/limits.yaml` 删 `direct_domains`、`real_browser` 段只留 `wait_sec`
- [x] 3.2 SKILL.md 中对 `direct_domains` 的引用同步为 site-fetch 清单表述

## 4. PreToolUse 拦截 hook + SessionStart 自愈

- [x] 4.1 `hooks/webfetch_gate.py`（Python，复用 `lib/fetch_routing`）：命中清单（capability != builtin-webfetch）每次硬拦 `deny` + 指明能力与命令；否则本 session 首次软拦、retry 放行；url 缺失/异常 fail-open
- [x] 4.2 `hooks/session_reset.py`：SessionStart 清本 plugin 的 session flag
- [x] 4.3 `hooks/hooks.json`：注册 PreToolUse matcher `WebFetch` + SessionStart，`${CLAUDE_PLUGIN_ROOT}` 引脚本
- [x] 4.4 `tests/test_webfetch_gate.py`：硬拦每次 + 不建 flag、软拦首次 + retry 放行、url 缺失 fail-open、bad json fail-open、reset 清 flag

## 5. skill 提示词双层改写

- [x] 5.1 SKILL.md frontmatter `description`：触发判据 + 排他指令前置，实现细节移入正文
- [x] 5.2 SKILL.md 正文「与内置 WebFetch 的关系」改写为「description + hook 双层」，删「Claude Code 无法拦截内置工具」过时句
- [x] 5.3 README 读 URL 触发方式同步（加 hook 动作点兜底说明）

## 6. 规格同步与验收

- [x] 6.1 `openspec validate --all` 通过（10/10）
- [x] 6.2 全量测试通过（`unittest discover -s tests -t .`：131 passed）；项目无 lint/type 配置，该项 N/A
- [ ] 6.3 归档前完工简报（拟加锁清单 + 值得沉淀知识）交用户确认 → `openspec archive`

## 7. 阶段二（后续 change，不在本次范围）

- [ ] 7.1 `site-fetch.txt` 接入 `~/.config/search-crew/` active + `pending/` + `promote` 生长，`MUST` 遵守 `config-lifecycle` 既有 locked 规则（仅经脚本写 active / promote 晋升 / changelog 留痕）——另起 change

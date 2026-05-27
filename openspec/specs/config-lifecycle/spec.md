# Config Lifecycle

`~/.config/search-crew/` 的全生命周期：首次安装从 plugin `defaults/` 拷贝、运行时只读 active、plugin 升级不动 active、pending 学习区 + Stop hook 提示。

## Purpose

让用户对自己的搜索偏好（routing、单价表、自定义适配器、自定义参数）拥有完全所有权——既不被 plugin 升级覆盖，也不会被 AI 在用户不知情下偷偷改。
## Requirements
### Requirement: ~/.config/search-crew/ 是 runtime 唯一配置真相
所有 subagent / skill 脚本 runtime MUST 只读 `~/.config/search-crew/`，**MUST NOT** 读 plugin 内置 `defaults/`（除首次安装 seed 那一次）。plugin 升级**不动** active；用户对 active 拥有完全所有权（可禁用 / 替换 / 重写任何系统默认行为）。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-21

#### Scenario: 用户改 routing.yaml
- **WHEN** 用户编辑 `~/.config/search-crew/routing.yaml` 删掉一个主题
- **THEN** 下次跑搜索时 runtime 读到的就是改后的版本；plugin 内置 defaults 不参与

#### Scenario: plugin 升级
- **WHEN** plugin 从 v0.1 升到 v0.2，内置 `defaults/routing.yaml` 加了一个新主题
- **THEN** `~/.config/search-crew/routing.yaml` 不被覆盖；用户想要新主题需要主动去 plugin 仓库 cd 查看再手动合并

### Requirement: 首次安装拷贝 defaults，幂等
plugin 安装时 `seed_user_config.py` MUST 把 `defaults/` 整个拷到 `~/.config/search-crew/`。**幂等**：已存在的子文件 MUST NOT 覆盖。运行时入口检测到 active 目录不存在时 MUST 兜底再跑一次 seed（带文件锁防并发）。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-21

#### Scenario: 首次 seed
- **WHEN** plugin 第一次安装，`~/.config/search-crew/` 不存在
- **THEN** seed 后该目录含 `routing.yaml` / `pricing.yaml` / `limits.yaml` / `adapters/`

#### Scenario: 二次 seed 不覆盖
- **WHEN** 用户已 seed 过，修改了 `routing.yaml`，重新运行 seed
- **THEN** 用户改动保留，不被覆盖

#### Scenario: 运行时兜底 seed
- **WHEN** 某 subagent 运行时发现 active 目录不存在（用户手动删了）
- **THEN** subagent 入口自动调 `seed_user_config.py` 重建，再继续

### Requirement: AI 永不直接改 active 配置
AI **MUST NOT** 直接修改 `~/.config/search-crew/` 下任何文件。要建议改动 MUST 写到 `~/.config/search-crew/pending/{routing,adapters}/<timestamp>-<slug>.yaml`，由 Stop hook 提示用户审核晋升。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-21

#### Scenario: AI 学到新路由
- **WHEN** AI 在使用中发现一条好用的新路由
- **THEN** 把候选规则写到 `~/.config/search-crew/pending/routing/<timestamp>-<slug>.yaml`，**不**直接改 `routing.yaml`

### Requirement: Pending 学习区 + Stop hook 提示
Stop hook 在主 agent 工作告一段落时 MUST 扫描 `~/.config/search-crew/pending/`，发现非空时输出简洁提示给用户，询问三选一：晋升 / 丢弃 / 暂留。用户全程**无需记任何命令**——交互入口在 Stop hook 自动提示里。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-21

#### Scenario: pending 非空时提示
- **WHEN** 主 agent 完成一次任务，Stop hook 触发，`pending/` 下有 2 条新规则
- **THEN** 用户在下一轮看到提示「💡 Search Crew 学习区有新的候选规则：2 条……是否要：1) 晋升 2) 丢弃 3) 暂留」

#### Scenario: pending 来源标注
- **WHEN** 本次 run 用了 pending 中的某条规则
- **THEN** 产物中显式标注「来自 pending，未确认」，让用户区分

### Requirement: Onboarding 时提示备份 active 目录
`/search-skill-setup`（插件命名空间下为 `/search-crew:search-skill-setup`）首次运行时 MUST 醒目提示用户：`~/.config/search-crew/` 是长期沉淀；强烈建议放 iCloud / Dropbox / dotfiles 仓库（原位置改软链接），或定期手动备份。提示同步写入 `~/.config/search-crew/backup-info.md` 让用户随时能查。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-26

#### Scenario: 首次 /search-skill-setup
- **WHEN** 用户首次跑 `/search-skill-setup` 命令
- **THEN** 输出中含醒目的备份建议段落（不是淹没在长 text 中间一行）；`backup-info.md` 已写入 active 目录

### Requirement: chrome-devtools-mcp 通过 plugin.json 自动拉起
Plugin MUST 通过 `.claude-plugin/plugin.json` 的 `mcpServers.chrome-devtools` 字段声明 `npx -y chrome-devtools-mcp@latest`，让 Claude Code 安装 plugin 时自动拉起。无需用户额外配置。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-21

#### Scenario: 安装 plugin 自动启动 MCP
- **WHEN** 用户跑 `/plugin install search-crew@search-crew`
- **THEN** Claude Code 按 plugin.json 自动启动 chrome-devtools-mcp 进程；用户首次使用 site-search 走浏览器路径时直接可用（前提是本机有 Chrome）


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

### Requirement: AI 写 active 仅经固定脚本操作，禁止手改
AI **MUST NOT** 用编辑器（free-form 编辑）修改 `~/.config/search-crew/` 下任何文件。AI 对 active 的写入 **MUST** 只经以下固定脚本操作之一，别无他途：①`seed`（首次拷 defaults）②`merge`（补缺失 defaults 顶层段）③`promote`（pending → active）。其中 `merge` 与 `promote` **MUST** 仅在用户显式授权后执行；`seed` 是首次安装/兜底自动行为。AI 自发产生的建议（学到的路由 / 适配器）**MUST** 仍写 `pending/`，**MUST NOT** 经任何途径直接进 active。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-28

#### Scenario: AI 不手改 active
- **WHEN** 用户授权 AI 补一个缺失的配置段
- **THEN** AI 跑 `seed_user_config.py --merge` 脚本完成，而非用编辑器打开 active 文件手改

#### Scenario: AI 自发建议仍走 pending
- **WHEN** AI 在使用中发现一条好用的新路由
- **THEN** 写到 `pending/routing/<timestamp>-<slug>.yaml`，不经 merge/promote 直接进 active

### Requirement: 每次脚本写入 active 追加 changelog
seed / merge / promote 任一脚本操作成功写入 active 后，**MUST** 向 `~/.config/search-crew/changelog.log` 追加一条记录，含：UTC 时间戳、操作类型、目标文件、改动摘要、触发来源。该 log **MUST** 由脚本写入（带文件锁），AI **MUST NOT** 手写。用户手改文件无法感知，不在 changelog 承诺范围内。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-28

#### Scenario: merge 记一条
- **WHEN** `merge` 给 `limits.yaml` 补了 `wide_search` 段
- **THEN** changelog.log 追加一行形如 `<ts> merge limits.yaml +wide_search trigger=setup`

#### Scenario: 晋升记一条
- **WHEN** 用户确认晋升一条 pending 路由
- **THEN** `promote` 把它并进 `routing.yaml` 并向 changelog 追加 `<ts> promote routing.yaml +topic:<name> trigger=user-approved`

### Requirement: pending 晋升经 promote 脚本执行
pending → active 的晋升 **MUST** 经 `promote` 脚本完成（文本块合并：routing 片段追加进 `topics:`，adapter 文件移入 `adapters/`），**MUST NOT** 由 AI 手改 active 文件完成。promote 成功后 **MUST** 删除已消费的 pending 文件；遇格式不符 / 重名 / 定位失败 **MUST** 报错且不留半成品。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-28

#### Scenario: 晋升一条 routing 候选
- **WHEN** 用户对某条 pending routing 候选选「晋升」
- **THEN** promote 把该 topic 项追加进 `routing.yaml` 的 `topics:`，删除该 pending 文件，记 changelog

#### Scenario: adapter 重名不覆盖
- **WHEN** promote 一个 adapter，但 `adapters/` 已有同名文件
- **THEN** promote 报错并中止，不覆盖用户已有文件

### Requirement: setup 检测缺段并在用户确认后跑 merge
`/search-skill-setup` 检查阶段 **MUST** 跑 `merge --dry-run` 检测 active 相对 defaults 缺哪些顶层段；有缺时 **MUST** 先向用户说明并征求确认，用户确认后由 **AI 自己执行** `merge`（脚本自解析路径），**MUST NOT** 让用户手敲依赖 `$CLAUDE_PLUGIN_ROOT` 的命令。无缺段时静默不打扰。

#### Scenario: 检测到缺段
- **WHEN** plugin 升级带来新 defaults 段、active 尚缺
- **THEN** setup 报告缺哪些段并问用户是否补齐，确认后 AI 跑 merge 并告知 changelog 已记

#### Scenario: 无缺段静默
- **WHEN** active 已与 defaults 同步
- **THEN** setup 不就配置补齐一事打扰用户


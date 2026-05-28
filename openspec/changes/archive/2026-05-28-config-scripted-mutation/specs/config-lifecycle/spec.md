## REMOVED Requirements

### Requirement: AI 永不直接改 active 配置
**Reason**: 绝对禁令在"用户显式授权"场景下太死（缺 defaults 段补不了、pending 晋升只能 AI 手改），由下方「AI 写 active 仅经固定脚本操作」取代——双通道模型：自发建议仍走 pending，授权维护走固定脚本 + changelog。
**Migration**: 行为更严不更松：AI 仍 MUST NOT 用编辑器手改 active；新增的写入途径只有受限的 seed/merge/promote 脚本操作，且全部记 changelog。

## ADDED Requirements

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

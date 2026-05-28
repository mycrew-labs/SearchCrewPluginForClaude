## MODIFIED Requirements

### Requirement: 首次安装拷贝 defaults，幂等
plugin 安装时 `seed_user_config.py` MUST 把 `defaults/` 整个拷到 `~/.config/search-crew/`。**幂等**：已存在的子文件 MUST NOT 覆盖。运行时入口检测到 active 目录不存在时 MUST 兜底再跑一次 seed（带文件锁防并发）。seed 操作除拷 defaults 外，也负责写入**初始化期用户选择的配置项**（如 `ai_summary.fast_default`）——经 `seed_user_config.py --set-fast-default <值>` 子模式写入对应字段并记 changelog；这仍属 seed 这一个固定写入操作，不新增第四个操作（沿 I-LEARN-001 的固定脚本写入约束）。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-29

#### Scenario: 首次 seed
- **WHEN** plugin 第一次安装，`~/.config/search-crew/` 不存在
- **THEN** seed 后该目录含 `routing.yaml` / `pricing.yaml` / `limits.yaml` / `adapters/`

#### Scenario: 二次 seed 不覆盖
- **WHEN** 用户已 seed 过，修改了 `routing.yaml`，重新运行 seed
- **THEN** 用户改动保留，不被覆盖

#### Scenario: 运行时兜底 seed
- **WHEN** 某 subagent 运行时发现 active 目录不存在（用户手动删了）
- **THEN** subagent 入口自动调 `seed_user_config.py` 重建，再继续

#### Scenario: 初始化期写用户选择的引擎
- **WHEN** 用户在 setup 选了快答默认引擎（如 gemini），主 agent 跑 `seed_user_config.py --set-fast-default gemini`
- **THEN** active `routing.yaml` 的 `ai_summary.fast_default` 被设为 `gemini`，changelog 追加一条；用户已有其它内容不动

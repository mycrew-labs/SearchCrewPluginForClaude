## REMOVED Requirements

### Requirement: 唯一显式 slash command 是 `/deep-search`
**Reason**: 命令改名归入 `search-*` 体系，避免裸 `/deep-search` 占用全局命令名；由下方 `唯一显式搜索 slash command 是 /search-deep` 取代。
**Migration**: 用户改用 `/search-deep`（或完整命名空间 `/search-crew:search-deep`）；行为不变，仅命令短名变更。

## ADDED Requirements

### Requirement: 唯一显式搜索 slash command 是 /search-deep
系统 SHALL 仅提供一个用户显式触发的搜索 slash command：`/search-deep <主题>`（插件命名空间下为 `/search-crew:search-deep`），用于强制启动 deep-search 流。其余搜索场景 MUST 由对话语义自动判断派发。命令的短名 MUST 用 `search-*` 前缀，避免占用 `/deep-search`、`/setup` 这类通用全局名。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-26

#### Scenario: 用户输入 /search-deep 跟主题
- **WHEN** 用户输入 `/search-deep 调研开源 LLM 推理框架`
- **THEN** 主 agent 派出 deep-search subagent 处理该主题（subagent 名仍为 deep-search，未改）

#### Scenario: 不存在通用 /search 或裸 /deep-search
- **WHEN** 用户尝试 `/search ...`
- **THEN** Claude Code 报告该命令不存在；真正的命令是 `/search-deep`（或 `/search-crew:search-deep`）

### Requirement: 主 agent 读 URL 优先用 web-page-fetch skill
主 agent 在需要读取具体 URL 的页面 / 文件内容时 SHALL 优先经 `web-page-fetch` skill 调 `fetch.py`，而非直接用内置 WebFetch；仅在 `fetch.py` 返回 `WEBFETCH_FALLBACK` 时回落内置 WebFetch，返回 `anti_bot` 时诚实失败。此偏好为软引导（Claude Code 无法物理禁用内置 WebFetch），靠 skill description + 本 requirement 落实。

#### Scenario: 主 agent 读 URL
- **WHEN** 用户给出一个 URL 要求读取内容
- **THEN** 主 agent 优先调 `fetch.py`（web-page-fetch skill 指引），按其三态结果处理

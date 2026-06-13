# orchestration Specification（delta）

## MODIFIED Requirements

### Requirement: 主 agent 读 URL 优先用 web-page-fetch skill

主 agent 在需要读取具体 URL 的页面 / 文件内容时 SHALL 优先经 `web-page-fetch` skill 调 `fetch.py`，而非直接用内置 WebFetch；仅在 `fetch.py` 返回 `WEBFETCH_FALLBACK` 时回落内置 WebFetch，返回 `anti_bot` 时诚实失败。此优先由**双层**落实：(1) skill `description` 触发层（软引导）；(2) plugin 自带的 PreToolUse hook 在主 agent 实际调内置 WebFetch 时做动作点兜底（详见 web-page-fetch 能力的「PreToolUse hook 按 mapping 分级拦截内置 WebFetch」需求）。先前「Claude Code 无法物理禁用内置 WebFetch、只能软引导」的表述不再成立——hook 可拦截内置工具。

#### Scenario: 主 agent 读 URL
- **WHEN** 用户给出一个 URL 要求读取内容
- **THEN** 主 agent 优先调 `fetch.py`（web-page-fetch skill 指引），按其三态结果处理

#### Scenario: 主 agent 漏走 fetch.py 时被 hook 纠回
- **WHEN** 主 agent 未经 fetch.py、直接对一个 URL 发起内置 WebFetch
- **THEN** PreToolUse hook 按 mapping 分级拦截（命中站点硬拦、其余首次软拦），将主 agent 纠回 `fetch.py`

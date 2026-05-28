## ADDED Requirements

### Requirement: /search-fast 默认引擎可由 fast_default 固定
`ai_search.py` 选 AI 源时 MUST 读 `~/.config/search-crew/routing.yaml` 的 `ai_summary.fast_default`：
- 值为具体家（`grok` / `gemini` / `doubao`）且该家可用 → **强制用它，无视语言/语境**。
- 值为 `auto`（默认）、缺失、或指定家不可用 → 回落按语言/语境 + `selection_order` 选（中文偏 doubao、英文偏 grok/gemini）。

用户可在 `/search-skill-setup` 交互选择该默认引擎，由 `seed_user_config.py --set-fast-default` 写入（不手改 active）。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-29

#### Scenario: 固定 gemini
- **WHEN** `ai_summary.fast_default: gemini`，用户 `/search-fast 国产新能源车`（中文）
- **THEN** ai_search 用 gemini（不因中文转 doubao）

#### Scenario: auto 仍按语言
- **WHEN** `fast_default: auto`（或缺失），中文 query
- **THEN** 按现有逻辑优先 doubao

#### Scenario: 指定家不可用时回落
- **WHEN** `fast_default: gemini` 但 `GEMINI_API_KEY` 未配
- **THEN** ai_search 回落语言/语境 + selection_order，不报错

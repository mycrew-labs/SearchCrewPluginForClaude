## Why

`/search-fast` 现在按语言自动选 AI 源（中文→doubao、英文→selection_order 的 grok/gemini）。但有用户希望**中英文都固定用某一家**（如都用 gemini）——目前无开关。

## What Changes

- **`routing.yaml` 加 `ai_summary.fast_default`**：取值 `auto`（默认，现行为）/ `grok` / `gemini` / `doubao`。设具体家 = 快答**无视语言强制用它**。
- **`ai_search.py` honor 它**：`fast_default` 是具体家且可用 → 用它（覆盖语言判断）；`auto` 或该家不可用 → 回落现有语言/语境逻辑。
- **`seed_user_config.py --set-fast-default <auto|grok|gemini|doubao>`**：seed 脚本新增子模式，把用户在初始化时选的这个值写进 active `routing.yaml` 的 `ai_summary.fast_default`，记 changelog。**框架定位**：这是 seed 期的「用户填的初始化配置项」，由 seed（三大固定写入操作之一）负责，不新增第四个操作、不破 I-LEARN-001。
- **setup 加一环**：用 AskUserQuestion 问「快答默认引擎」（auto / 都用 gemini / 都用 doubao / 都用 grok），用户选完跑 `seed_user_config.py --set-fast-default <choice>` 写入。

## Capabilities

### Modified Capabilities

- `config-lifecycle`：MODIFY「首次安装拷贝 defaults」——明确 seed 操作除拷 defaults 外，也负责写「初始化期用户选择的配置项」（如 `fast_default`），经 `--set-fast-default` 子模式 + changelog，仍属 seed 这一个固定操作。
- `fast-search`：ADD「/search-fast 默认引擎可由 `ai_summary.fast_default` 固定；auto 时按语言选」。

## Impact

- **locked 影响**：MODIFY config-lifecycle「首次安装拷贝 defaults」locked（扩 seed 职责含 init 配置写入）；ADD fast-search 一条。归档前确认。
- **代码**：`routing.yaml`（defaults + 注释）；`ai_search.py`（读 fast_default 覆盖选源）；`seed_user_config.py`（`--set-fast-default` 子模式，改 ai_summary 块内 fast_default 行 + changelog）；`commands/search-skill-setup.md`（加选引擎环节）。
- **向后兼容**：默认 `auto` = 完全现行为；老用户 active 无 `fast_default` 段时 ai_search 视为 auto。
- **不破 I-LEARN-001**：写入经 seed 脚本（固定操作），非 AI 手改；用户在 setup 显式选择即授权。

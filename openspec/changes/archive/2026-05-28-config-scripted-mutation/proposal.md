## Why

charter 不变量 `I-LEARN-001`（locked）现在是绝对禁令：「AI **永不**直接修改 active 配置；建议改动写 `pending/` 由用户晋升」。它防的是 AI 在用户不知情下偷偷改偏好——这个意图正确，但字面留了两个问题：

1. **letter 太死**：plugin 升级后 active 缺了新的 defaults 顶层段（如本次 `wide_search.max_items`），用户想补，AI 却无合规途径——只能让用户手跑一条依赖 `$CLAUDE_PLUGIN_ROOT` 的命令（实测在交互 shell 里该变量为空，命令直接报错），或 AI 违规手改（本会话已踩过一次）。
2. **晋升这一步自己在漏**：Stop hook 只*提示*晋升，真正把 pending 规则并进 active 是 **AI 手改 `routing.yaml`** 完成的——这恰恰违反了 I-LEARN-001 想堵的"AI 手碰 active"。

根因：缺一个「**用户授权 → 经固定脚本操作 → 留痕**」的合规写入通道。本 change 把 active 的写入收敛成有限几个脚本化原子操作，并加修改日志，既解除"用户授权下也不能改"的死结，又用脚本保证修改精准（LLM 不会顺手动到无关内容）。

## What Changes

- **重定义 `I-LEARN-001`（charter，用户拍板）+ config-lifecycle locked 需求**：从「AI 永不直接改 active」改为**双通道模型**：
  - **AI 自发建议**（学到的路由 / 适配器）→ 仍写 `pending/`，永不直接进 active（不变）。
  - **用户显式授权的维护** → AI 可写 active，但**只能经约定好的固定脚本操作**，**禁止用编辑器手改任何 active 文件**。
- **明确 active 的三个固定写入操作**，是 AI 写 active 的**唯一**途径：
  - `seed`（首次拷 defaults，已有）
  - `merge`（补缺失 defaults 顶层段，已有；新增 `--dry-run` 只报不写）
  - `promote`（pending → active，**新建脚本**，替代现在的 AI 手改）
- **新增 changelog**：每次经脚本写入 active 都追加 `~/.config/search-crew/changelog.log`（时间 / 操作 / 改了什么 / 触发来源）。覆盖 seed / merge / promote 三类自动行为；用户手改文件无法感知、不记。AI 永不手写该 log。
- **setup 流程升级**：检查阶段跑 `merge --dry-run` 检测缺段 → 有缺则问用户 → 用户确认后 **AI 自己跑 `merge`**（脚本自解析路径，不再给用户贴会报错的命令）。

## Capabilities

### Modified Capabilities

- `config-lifecycle`：MODIFY locked 需求「AI 永不直接改 active 配置」为双通道模型；ADD「固定脚本操作是 AI 写 active 的唯一途径」「每次脚本写入追加 changelog」「pending 晋升经 promote 脚本」「setup 检测缺段并在用户确认后跑 merge」。同时 charter `USER_DESIGN.md` 的 `I-LEARN-001` 需相应改写（用户所有，归档前确认）。

## Impact

- **代码/产物**：`seed_user_config.py` 加 `--dry-run` + changelog 写入；新建 `promote.py` 实现 pending→active 合并 + changelog；`lib/` 加 changelog 写入辅助、`_split_top_level_blocks` 下沉到 `lib/` 供两脚本共用；`commands/search-skill-setup.md` 升级检测/确认/执行流程；`stop_hook.py` 的晋升提示话术指向 promote 脚本。
- **locked 影响**：MODIFY charter `I-LEARN-001`（user-owned）+ config-lifecycle「AI 永不直接改 active」（user-confirmed 锁）。归档前按锁确认 gate 提请用户确认。
- **向后兼容**：pending 学习区、Stop hook 提示、首次 seed 行为不变；只是晋升从"AI 手改"变成"脚本执行 + 记 log"。
- **安全/信任**：写入收敛到固定脚本 + 全程留痕，比现在"AI 手改"更可控、可审计。

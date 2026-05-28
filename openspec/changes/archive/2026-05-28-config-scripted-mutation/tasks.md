## 1. charter / 不变量改写（用户所有，先确认）

- [x] 1.1 改写 `openspec/USER_DESIGN.md` 的 `I-LEARN-001` 为双通道模型（自发建议→pending；授权维护→固定脚本+changelog；禁手改）——**MUST 先经用户确认再落**

## 2. 脚本：固定写入操作 + changelog（lib + seed_user_config.py）

- [x] 2.1 `lib/` 加 `append_changelog(op, target, summary, trigger)` 辅助：追加写 `~/.config/search-crew/changelog.log`，带文件锁，UTC 时间戳
- [x] 2.2 `seed`（无参）成功后调 changelog 记一条（trigger=first-install / fallback）
- [x] 2.3 `--merge` 成功补段后对每个改动文件记 changelog（trigger 由调用方透传，默认 manual）
- [x] 2.4 `--merge --dry-run`：只算缺失顶层段、不写盘，stdout 输出机器可读结果（每文件缺哪些段）
- [x] 2.5 把 `_split_top_level_blocks` 从 `seed_user_config.py` 下沉到 `lib/`，两脚本共用
- [x] 2.6 新建 `promote.py <pending-file>`（单独脚本）：routing 片段追加进 `routing.yaml` 的 `topics:` 块；adapter 文件移入 `adapters/`（重名报错不覆盖）；成功后删 pending 文件 + 记 changelog；坏格式/定位失败报错不留半成品
- [x] 2.7 各脚本支持 `--trigger <name>` 可选参数：标注触发来源写进 changelog（setup / user-approved 等）

## 3. 命令 / hook 文案

- [x] 3.1 `commands/search-skill-setup.md`：检查阶段改为跑 `--merge --dry-run` → 有缺段用 AskUserQuestion 问用户 → 确认后 AI 自己跑 `--merge`；删掉让用户手敲 `$CLAUDE_PLUGIN_ROOT/...` 的旧写法
- [x] 3.2 `stop_hook.py` 晋升提示话术：指向"由 AI 跑 promote 脚本完成晋升"，而非 AI 手改

## 4. 测试

- [x] 4.1 `tests/` 加 changelog 追加测试（格式 / 追加不覆盖 / 并发锁）
- [x] 4.2 `--merge --dry-run` 检测缺段测试（有缺 / 无缺）
- [x] 4.3 `--promote` 测试：routing 片段并入 topics、adapter 移入、重名报错、坏格式报错、成功后删 pending、记 changelog
- [x] 4.4 `tests/MANUAL.md` 补：setup 检测缺段→问→AI 跑 merge；晋升经 promote 脚本；changelog 三类记录可见

## 5. 文档同步

- [x] 5.1 README / EXTENDING / `defaults/limits.yaml` 或 routing.yaml 顶部注释里凡是写「AI 永不自动改本文件 / 写 pending」的措辞，按双通道模型校准（仍强调不手改，但说明授权下经脚本可写 + 有 changelog）

## 6. 归档前：锁确认 gate

- [x] 6.1 `openspec validate config-scripted-mutation --strict` 通过
- [x] 6.2 完工简报：本次 MODIFY charter `I-LEARN-001`（user-owned）+ config-lifecycle locked「AI 永不直接改 active」；新「AI 写 active 仅经固定脚本」「changelog」「promote 晋升」「setup 检测缺段」拟落 user-confirmed 锁；逐条跟用户确认
- [x] 6.3 用户确认 → 落锁 + 改 charter → bump version → `openspec archive config-scripted-mutation` → commit → push
- [ ] 6.4 **manual** · reload 后实测：setup 跑（看是否检测缺段+问+自动 merge）；造一条 pending 走晋升（看 promote + changelog）；cat changelog.log 看三类记录

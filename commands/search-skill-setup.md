---
name: search-skill-setup
description: 检查 Search Crew plugin 的配置状态、API key 可用性、Chrome / MCP 可用性，并给出引导。
---

## 主 agent 工作流

### 1. 跑 backend 检查

```bash
python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/check_backends.py
```

按 JSON 输出汇报：

- 可用 backend
- 未配置 backend（给注册 URL + `~/.zshrc` 配置模板）
- **AI 综述 backend**（`ai_summary_backends` 段）：三家 grok / gemini / doubao 各自状态；任一可用即整层可用；全未配会自动回落 jina——这种情况下务必在汇报里指出「可选的 AI 综述层未启用，缺失：`GROK_API_KEY` / `GEMINI_API_KEY` / `DOUBAO_API_KEY`」
- Chrome 是否装了（mac: `mdfind kMDItemCFBundleIdentifier == com.google.Chrome`；linux: `which google-chrome chromium`）
- chrome-devtools-mcp 是否能起（`npx chrome-devtools-mcp@latest --version`）

### 2. 检查 active 配置目录

```bash
ls ~/.config/search-crew/ 2>&1 || echo "未初始化"
```

- 如果不存在 / 缺关键文件 → 调种子拷贝：
  ```bash
  python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/seed_user_config.py
  ```
- 如果 active 已存在但 plugin 升级带来新顶层段（例如 `ai_summary:` / `call_cap:`）→ 跑 merge：
  ```bash
  python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/seed_user_config.py --merge
  ```
  仅追加缺失的顶层段，用户已有内容一字不动。

### 3. 醒目展示 onboarding 备份提示（P-CONFIG-001）

首次运行 setup 时**必须**向用户展示（多次跑也建议每次都给）：

```
⚠️ 重要：~/.config/search-crew/ 是你长期沉淀的偏好
   - 路由起点、自定义适配器、晋升过的 pending 规则都在这里
   - **强烈建议**：
     1. 把它放到一个会同步备份的目录（iCloud / Dropbox / 你自己的 dotfiles 仓库），原位置改成软链接；或
     2. 定期手动备份
   - 否则一旦本地丢失，你长期沉淀的偏好就找不回来了
```

### 4. 激活仓库内 git hook（每个 clone 一次）

仓库内 `.githooks/pre-commit` 在 commit 前自动检查「OpenSpec change 已完成实施但未归档」的状态。脚本随仓库走，但每个新 clone 都要跑一次激活命令：

```bash
git config core.hooksPath .githooks
```

`git config --local --get core.hooksPath` 输出 `.githooks` 即生效。

不激活也能正常 commit，只是失去归档检查。

### 5. Stop hook 注册引导（可选但推荐）

向用户展示如何把 `stop_hook.py` 接到 Claude Code，让 pending 学习区在每次主 agent 工作结束时自动提示：

```
【可选】注册 Stop hook：

在 ~/.claude/settings.json 的 hooks.Stop 数组里加：

{
  "hooks": {
    "Stop": [
      {
        "command": "python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/stop_hook.py"
      }
    ]
  }
}

（具体字段以你本机 Claude Code 版本为准；改完重启 Claude Code 生效）
不注册也行——只是 pending 学习区不会自动提示，你可以手动 cat ~/.config/search-crew/pending/ 看。
```

### 6. 提示用户重新加载

如果用户刚改了 `~/.zshrc`：

```
配置完后请：
  source ~/.zshrc
  然后重新打开 Claude Code 让 plugin 拿到新环境变量
```

### 7. 测试建议

```
快速测试：
  对话直接说：「查一下当前最流行的开源 LLM 推理框架」（关键词触发 fast-search，无需 slash command）

站内搜索测试（需要 Chrome）：
  对话说：「去 react.dev 查 Suspense 的最新用法」（关键词触发 site-search）

深度调研测试：
  /search-deep 深入调研开源 LLM 推理框架的现状和趋势

查看历史使用：
  ! python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/usage.py --last 10
```

## 关键约束

- 必跑 backend 检查；不允许跳过假装一切正常
- 配置目录不存在必走 seed
- 备份提示必须醒目（不是淹没在一段长 text 中间的一行）

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

- 如果不存在 / 缺关键文件 → 调种子拷贝（首次 seed）：
  ```bash
  python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/seed_user_config.py
  ```
- 如果 active 已存在 → **先用 `--dry-run` 检测**是否缺新顶层段（plugin 升级常带来，如 `wide_search:`）：
  ```bash
  python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/seed_user_config.py --merge --dry-run
  ```
  - **有缺段**（stdout 输出 `<file>\t<缺的key>`）→ **MUST 先问用户**（用 AskUserQuestion，说明缺哪些段、补齐只追加不动已有内容），用户确认后 **由你（主 agent）自己执行**真正的 merge：
    ```bash
    python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/seed_user_config.py --merge --trigger setup
    ```
    执行后告知用户「已补齐 X 段，已记入 `~/.config/search-crew/changelog.log`」。
  - **无缺段** → 静默，不打扰。
  - **MUST NOT** 把 `seed_user_config.py --merge` 这条命令直接丢给用户在 `!` shell 里跑——交互 shell 里 `$CLAUDE_PLUGIN_ROOT` 可能为空会报错；脚本你来跑（脚本自身用 `__file__` 解析路径，不依赖该变量）。
  - **MUST NOT** 用编辑器手改 `~/.config/search-crew/` 任何文件（charter I-LEARN-001）；补配置只能经 seed / merge / promote 这三个固定脚本操作。

### 3. 选 /search-fast 快答默认引擎

用 AskUserQuestion 问用户「`/search-fast` 默认用哪个 AI 引擎」，给 4 个选项：

- **auto（推荐）**：按语言自动选——中文偏 doubao、英文偏 grok/gemini
- **都用 gemini**：中英文都固定 gemini（全球综述均衡）
- **都用 doubao**：中英文都固定 doubao（中文最强）
- **都用 grok**：中英文都固定 grok（英文舆论 / 实时）

用户选完，**由你（主 agent）自己跑**脚本写入（seed 期初始化配置，不手改 active）：

```bash
python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/seed_user_config.py --set-fast-default <auto|gemini|doubao|grok>
```

读取当前值可看 `~/.config/search-crew/routing.yaml` 的 `ai_summary.fast_default`。用户没明确想改时可跳过（默认 auto）。

### 4. 醒目展示 onboarding 备份提示（P-CONFIG-001）

首次运行 setup 时**必须**向用户展示（多次跑也建议每次都给）：

```
⚠️ 重要：~/.config/search-crew/ 是你长期沉淀的偏好
   - 路由起点、自定义适配器、晋升过的 pending 规则都在这里
   - **强烈建议**：
     1. 把它放到一个会同步备份的目录（iCloud / Dropbox / 你自己的 dotfiles 仓库），原位置改成软链接；或
     2. 定期手动备份
   - 否则一旦本地丢失，你长期沉淀的偏好就找不回来了
```

### 5. 激活仓库内 git hook（每个 clone 一次）

仓库内 `.githooks/pre-commit` 在 commit 前自动检查「OpenSpec change 已完成实施但未归档」的状态。脚本随仓库走，但每个新 clone 都要跑一次激活命令：

```bash
git config core.hooksPath .githooks
```

`git config --local --get core.hooksPath` 输出 `.githooks` 即生效。

不激活也能正常 commit，只是失去归档检查。

### 6. Stop hook 注册引导（可选但推荐）

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

### 7. 提示用户重新加载

如果用户刚改了 `~/.zshrc`：

```
配置完后请：
  source ~/.zshrc
  然后重新打开 Claude Code 让 plugin 拿到新环境变量
```

### 8. 测试建议

```
快答测试：
  /search-fast 当前最流行的开源 LLM 推理框架（AI 综述快答，秒级）
  或对话直接说「查一下…」也会自动走快答

站内搜索测试（需要 Chrome）：
  对话说：「去 react.dev 查 Suspense 的最新用法」（关键词触发 site-search）

深度调研测试（显式）：
  /search-deep 深入调研开源 LLM 推理框架的现状和趋势

批量对照测试（显式）：
  /search-wide 对比这 5 个开源向量数据库的性能/许可证/部署难度

查看历史使用：
  ! python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/usage.py --last 10
```

### 9. 进阶（可选）：远程 browser-host

> 默认关闭，绝大多数用户用不到，**不要**主动引导普通用户配。仅当用户明确要抓「登录墙 / 付费墙」内容（如付费 paper PDF）且已自建 browser-host 时才提。

web-page-fetch 遇到 `needs_auth`（登录 / 付费墙）默认走 `on_blocked` 策略（honest / collaborate）。若用户在一台带桌面的 Linux 上跑了 [opencli-browser-host](https://github.com/mycrew-labs)（用真实登录态浏览器抓取 + frp 暴露的 HTTP API），可在 `~/.config/search-crew/limits.yaml` 的 `web_page_fetch.remote_host` 填端点 + basic auth 启用之。

- **客户端已接好**（fetch.py 抓取链已含 opencli-remote 层，`enabled: true` + 填 endpoint 即生效）；**服务端**需你自建 opencli-browser-host（backlog B-006）。
- 安全提醒：该 API 背后是登录态真实浏览器；只暴露带鉴权 + 只读收窄的 HTTP 包装，别裸暴露 daemon。

setup 检查到 `remote_host.enabled: true` 时，可顺带 `curl <endpoint>` 探一下连通性并告知用户。

## 关键约束

- 必跑 backend 检查；不允许跳过假装一切正常
- 配置目录不存在必走 seed
- 备份提示必须醒目（不是淹没在一段长 text 中间的一行）

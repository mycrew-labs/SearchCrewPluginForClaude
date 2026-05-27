# Manual TC 用例

需要 Claude Code runtime / 真实环境的验证项。每条按"做什么 → 期待什么"两段写。

## TC-CMD-001 ：触发方式

**做**：

1. 在 Claude Code 对话框输入「查一下当前最流行的开源 LLM 推理框架」（不带 slash command）
2. 在另一个对话输入 `/search-deep 深入调研开源 LLM 推理框架现状`
3. 尝试 `/search ...`（应不存在）；尝试 `--site ...`（应不被识别）

**期**：1 自动派 fast-search；2 派 deep-search；3 两者都"未识别"。

## TC-AGENT-001 ：三个 subagent 都做 ranking + 摘要

**做**：分别触发 fast / site / deep，看产物。

**期**：每个 subagent 的 `<run_root>/<name>/INDEX.md` 都含 ranking + 关键词清单。

## TC-AGENT-002 ：deep-search 工作模式

**做**：跑一次 `/search-deep`，看 `<run_root>/deep-search/`。

**期**：

- 有 `plan.md`（第一轮规划）
- 有 `round-1.md` / `round-2.md` ...
- 有 `traces/fast-search-<sid>/` 或 `traces/site-search-<sid>/`
- 最终有 `report.html` + `report.md`
- 不超过 5 轮（`max_rounds`）

## TC-AGENT-003 ：site-search 三级降级

**做**：

1. `/search` 关键词触发让 LLM 派 site-search → github.com（应走 API 适配器）
2. 派 site-search → 一个无适配器的官方文档站（应 fetch 静态 URL）
3. 派 site-search → 一个 SPA 站（应降级 MCP）

**期**：每个场景的产物 INDEX 中应能看出走的是哪一级（adapter 字段）。

适配器注册部分由 `test_adapter_registry.py` 自动覆盖。

## TC-ROUTE-001 ：循证四步

**做**：

- 关键词命中"学术论文"主题，模拟 arxiv 不通时看是否标"未在官方源验证"
- fast-search 派出去的结果，主 agent 在最终回复前应派 site-search 复核（看 TaskList）

**期**：未通过复核的内容在最终回复显式标注。

## TC-FALLBACK-001 ：零 key fallback

**做**：

```bash
unset JINA_API_KEY SERPER_API_KEY
python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/search.py --query test --max-results 3
```

**期**：stdout 输出 `"fallback": "WEBSEARCH_FALLBACK"`，进程 exit 0。

主 agent 此时应改用 WebSearch（manual 触发对话验证）。

## TC-DATA-001 ：产物目录与调用语义

**做**：跑一次 deep-search。

**期**：

- 所有产物在同一 `<run_root>` 下
- deep-search 派出去的 fast/site 子产物在 `<run_root>/deep-search/traces/` 下，**不**在独立的 session-id 目录
- 主 agent 给用户的回复**不含** `/tmp/search-crew/` 字符串

## TC-MCP-001 ：chrome-devtools-mcp 拉起

**做**：

```bash
/plugin install search-crew
```

**期**：Claude Code 自动拉起 npx chrome-devtools-mcp@latest。`/search-skill-setup` 报告 Chrome 是否装了。

## TC-PARALLEL-001 ：并行派发 + TaskCreate

**做**：跑 `/search-deep`，观察 task list。

**期**：

- 每轮的多个 subagent 在同一 message 内一次性发起 Task 调用
- 派发前已能在 TaskList 看到任务记录（描述面向用户而非「派 site-search worker」）

## TC-LEARN-001 ：Stop hook 提示

**做**：

```bash
mkdir -p ~/.config/search-crew/pending/routing
echo "site: fake.com" > ~/.config/search-crew/pending/routing/fake-rule.yaml
```

然后在 Claude Code 跑任意指令让 Stop hook 触发。

**期**：用户在下一轮看到来自 stop_hook.py 的提示（说有 N 条候选规则）。如果未配置 hook，至少手动跑 `python3 .../stop_hook.py < /dev/null` 应输出提示。

## TC-UX-001 ：subagent 启动协作邀请

**做**：跑 `/search-deep`。

**期**：在派发 subagent 之前主 agent 的可见文本里出现「💡 如果你已经知道权威数据源...」一行。

## TC-EVIDENCE-001 ：循证证据传递

**做**：跑 `/search-deep`，看主 agent 最终回复 + `report.md`。

**期**：每段结论后有 URL（结论性强的段含原文摘录 / 数字）。少 URL 视为缺陷。

## TC-CONTEXT-001 ：context 卫生

**做**：跑 `/search-deep` 完成后，grep 主 agent 最终回复内容。

**期**：

- 含且只含**一行** `📊 本次估算 ~$X.XXX USD（...）`
- **不含** `/tmp/search-crew/` 字符串
- **不含** `usage-summary.md` 字符串（如果用户主动问明细，主 agent Read 文件后才呈现）

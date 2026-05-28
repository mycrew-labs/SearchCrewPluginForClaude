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

## TC-DR-001 ：deep-search 按复杂度缩放 + 假设范围

**做**：跑一个简单 topic（如 `/search-deep 调研 React useTransition 用法`）和一个复杂跨域 topic，分别看 `<run_root>/deep-search/plan.md`。

**期**：

- plan.md 顶部含「本次假设范围 / 角度」声明
- plan.md 顶部含「复杂度评估 + 投入决策」一行（复杂度 / 本轮 worker 数 / 预计轮数）
- 简单 topic 用 1-3 个 worker、1-2 轮即收（不铺满 `per_round_breadth`、不跑到 `max_rounds`）
- 实际 worker 数 ≤ `per_round_breadth`、轮数 ≤ `max_rounds`

## TC-DR-002 ：派 worker 任务契约四要素

**做**：跑 `/search-deep`，看 deep-search 派 fast/site-search 的 Task prompt（traces 或 task list）。

**期**：每个派发 prompt 含明确的 目标 / 输出格式 / 工具源指引（含 routing 硬规则）/ 边界 四部分，缺任一视为缺陷。

## TC-DR-003 ：综合阶段标分歧 + 循证状态

**做**：跑一个易出多源冲突的对比 topic，看 `report.md` / `report.html`。

**期**：

- 多源对同一指标给出冲突数据时，报告显式呈现「⚠️ 分歧：源 A=X，源 B=Y」，而非只取其一
- 每条来自非官方源的关键结论标注「未在官方源验证」或「已复核」

## TC-DR-004 ：每轮 gap 评估

**做**：跑一个需多轮的 topic，看各 `round-N.md`。

**期**：每个 round-N.md 含「已覆盖 / 还缺 / 下一轮补哪个角度（或进入综合）」段，且下一步决策（继续 vs 收敛）与该评估一致。

## TC-DR-005 ：歧义 topic 主 agent 先问

**做**：

1. `/search-deep 调研 transformer`（范围过宽 / 歧义）
2. `/search-deep 对比 vLLM 与 TensorRT-LLM 的吞吐与显存`（已清晰）

**期**：1 主 agent 派发前先发一句话澄清（含合理默认，非阻塞）；2 主 agent 不额外提问，直接派 deep-search。

## TC-CONTEXT-001 ：context 卫生

**做**：跑 `/search-deep` 完成后，grep 主 agent 最终回复内容。

**期**：

- 含且只含**一行** `📊 本次估算 ~$X.XXX USD（...）`
- **不含** `/tmp/search-crew/` 字符串
- **不含** `usage-summary.md` 字符串（如果用户主动问明细，主 agent Read 文件后才呈现）

## TC-WIDE-001 ：派发前确认 schema（×N 闸）

**做**：`/search-wide 对比这 6 个开源向量数据库的性能/许可证/部署难度`

**期**：wide-search 在派任何 worker **之前**先抛回「对象清单（6 个）+ 列（性能/许可证/部署难度）」请用户确认；用户放行后才并行派 worker。

## TC-WIDE-002 ：一对象一 worker 并行 + 矩阵双格式

**做**：放行上面的 schema，跑完看产物。

**期**：

- 每个对象一个独立 worker（fast-search 为主），同 turn 并行派出
- 产 `report.md`（行=对象、列=维度的表格，每格附证据 anchor）+ `report.html`（可按列排序）+ `traces/`
- report.md 与 report.html 语义等价（标「未获取」的格两边一致）

## TC-WIDE-003 ：超 max_items 分批

**做**：`/search-wide` 给一个超过 `wide_search.max_items`（默认 12）的对象数（如 20 个）。

**期**：lead 分批处理或请用户收窄，**不**一次性铺超 max_items 个并行 worker。

## TC-WIDE-004 ：单点 worker 失败标「未获取」

**做**：跑一个其中某对象明显查不到数据的矩阵。

**期**：矩阵照常产出，查不到的对应格标「未获取」，其余行正常，不因单点失败放弃整表。

## TC-FAST-CMD-001 ：/search-fast 显式触发

**做**：`/search-fast 当前最流行的开源向量数据库`

**期**：主 agent 派一个 fast-search subagent 做单轮调研并回带证据的结论 + 一行 cost；语义自动触发的老路径（不打命令、通用查询语气）仍照常工作。

## TC-CFG-MUT-001 ：setup 检测缺段 → 问 → AI 自己 merge

**做**：删掉 active 某 yaml 的一个顶层段（模拟 plugin 升级落后），跑 `/search-skill-setup`。

**期**：

- setup 用 `--merge --dry-run` 报出缺哪些段
- 先用 AskUserQuestion 问你是否补齐（不直接补）
- 你确认后，**AI 自己**跑 `--merge --trigger setup`（不是丢给你一条 `$CLAUDE_PLUGIN_ROOT` 命令）
- 补齐后告知 `changelog.log` 已记一条

## TC-CFG-MUT-002 ：pending 晋升经 promote 脚本

**做**：在 `~/.config/search-crew/pending/routing/` 放一条候选（`- name: ...` 的 topics 项），对 AI 说「晋升它」。

**期**：

- AI 跑 `promote.py <file>`，把该 topic 合并进 `routing.yaml` 的 `topics:`（2 空格缩进），删除 pending 文件
- **不**用编辑器手改 routing.yaml
- `changelog.log` 追加 `promote routing.yaml +topic:<name> trigger=user-approved`

## TC-CFG-MUT-003 ：changelog 三类记录可见

**做**：依次触发首次 seed、一次 merge 补段、一次 promote 后，`cat ~/.config/search-crew/changelog.log`。

**期**：三行分别含 `seed (init) ... trigger=first-install`、`merge <file> +<seg> trigger=setup`、`promote routing.yaml +topic:<name> trigger=user-approved`，每行带 UTC 时间戳，且文件只追加不重写。

## TC-RUNID-001 ：一次派发 lead+worker 同 run 目录

**做**：`/search-deep <题>`，跑完后 `ls /tmp/search-crew/<本次run目录>/`。

**期**：

- 主 agent 派发前跑过 `run_paths.py --new` 造目录，并在 deep-search 的派发 prompt 里带了 `SEARCH_CREW_RUN_ROOT=<该目录>`
- deep-search 派 fast/site worker 时把同一 `SEARCH_CREW_RUN_ROOT` 传下去
- 该目录下同时有 lead 的 deep-search/ 产物、worker 的 traces/ 产物、**一份** usage.jsonl（含 lead+worker 所有调用）
- cost 一行 = 本次派发合计（含 worker），不与会话其它派发混

## TC-RUNID-002 ：两次 /search-fast 互不累计

**做**：连续跑两次 `/search-fast`，看各自 cost 行。

**期**：两次落不同 run 目录，cost 各自独立（第二次不把第一次的调用累计进来）。

## TC-SPLIT-001 ：/search-fast = AI 综述快答，无 subagent

**做**：`/search-fast 当前最流行的开源向量数据库`

**期**：主 agent **直接跑 `ai_search.py`**（不派任何 subagent），秒级返回一段 AI 综述 + 引用 URL + 一行 cost；产物里没有 `evidence-search-NNN.md` 那类结构化文件。

## TC-SPLIT-002 ：evidence-search 中英双语并发（deep 内部）

**做**：`/search-deep <一个中英文资料都丰富的题>`，看 deep 派出的 worker。

**期**：deep 派的是 **evidence-search**（非 fast-search）；evidence-search 同 turn 并发跑 serper(英文版) + bocha(中文版)，merge 去重；serper 失败才回落 jina；产物落 `<run_root>/evidence-search/`。

## TC-SPLIT-003 ：deep/wide 改派 evidence-search

**做**：分别跑 `/search-deep` 与 `/search-wide`。

**期**：两者派的 worker subagent 都是 `evidence-search`（SEARCH_CREW_SUBAGENT=evidence-search、产物前缀 evidence-search-），不再出现 fast-search。

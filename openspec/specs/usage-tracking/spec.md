# Usage Tracking

API 调用次数与估算成本的打点、汇总、永久持久化、独立查询。参考 [vibe-usage](https://www.npmjs.com/package/@vibe-cafe/vibe-usage) 的模式。

## Purpose

让用户每次拿到调研产物时能直接看到本次花了多少钱（次数 + 估算 cost），并保留所有原始打点供未来做更精细的统计——同时不污染主 agent 的 context。
## Requirements
### Requirement: 每次 run 必落 usage-summary.md
每次 backend 调用 MUST 落一条记录到 `<run_root>/usage.jsonl`。run 结束时 MUST 生成 `<run_root>/usage-summary.md`（人类可读 markdown，含 by_backend / by_subagent 拆分）。每个 subagent 结束前 MUST 在 `<run_root>/<subagent>/usage-summary.md` 写本 subagent 的切片摘要。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-21

#### Scenario: 一次完整调研
- **WHEN** 主 agent 跑完一次 deep-search 并调用 `finalize_usage.py <run_root>`
- **THEN** `<run_root>/usage.jsonl` 存在；`<run_root>/usage-summary.md` 存在，内含「调用总数 / 估算合计 / by_backend / by_subagent」段

#### Scenario: 各 subagent 切片
- **WHEN** fast-search 结束前调用 `finalize_usage.py --subagent fast-search <run_root>`
- **THEN** `<run_root>/fast-search/usage-summary.md` 存在，只含本 subagent 的 usage 切片

### Requirement: 主 agent 回复只追加一行 cost 总览
主 agent 在最终回复结尾 MUST 追加且仅追加**一行** cost 总览（形如 `📊 本次估算 ~$X.XXX USD（N 次调用）`）。**MUST NOT** 在回复里附路径、复述按 backend / subagent 的拆分。用户追问明细时主 agent SHALL Read `<run_root>/usage-summary.md` 后呈现拆分；run_root 路径由 subagent 派发时记下，不靠主 agent 自己回想字符串。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-21

#### Scenario: 默认回复只一行
- **WHEN** 主 agent 完成调研给用户最终回复
- **THEN** 回复结尾有且仅有一行 cost 总览；不出现 `/tmp/search-crew/`、不出现 `usage-summary.md` 字符串、不列按 backend 拆分

#### Scenario: 用户追问明细
- **WHEN** 用户在 cost 总览出现后说「按 backend 拆开看」
- **THEN** 主 agent 拼出 `<run_root>/usage-summary.md` 路径并 Read，把表格呈现给用户

### Requirement: 原始打点永久持久化到 ~/.local/state/search-crew/
每次打点 MUST 同步追加到 `~/.local/state/search-crew/calls.jsonl`；每次 run 结束 MUST 追加一行汇总到 `~/.local/state/search-crew/runs.jsonl`。这两个文件 MUST 永不自动清理 / 截断 / rotate——任何清理由用户主动做。**MUST NOT** 写入 `~/.config/search-crew/`（配置与统计语义分离）。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-21

#### Scenario: 跨 run 累积
- **WHEN** 完成两次独立调研
- **THEN** `~/.local/state/search-crew/calls.jsonl` 行数 = 两次 run 调用之和；`~/.local/state/search-crew/runs.jsonl` 增加 2 行

#### Scenario: 卸载 plugin 后数据仍在
- **WHEN** 用户卸载 plugin 然后重装
- **THEN** `~/.local/state/search-crew/{calls,runs}.jsonl` 不丢，历史数据完整可查

### Requirement: 单价表 pricing.yaml 用户可覆盖
plugin 内置 `defaults/pricing.yaml` 含基线单价；首次安装拷贝到 `~/.config/search-crew/pricing.yaml`；runtime 只读 active 版本；用户改 active 立即生效。某 backend / endpoint 单价未配置时 `cost_estimate_usd` MUST 为 `null`，`pricing_source` 标 `unknown`；usage-summary 中 MUST 显式标注「⚠️ 以下调用单价未知，未计入合计」。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-21

#### Scenario: 用户改单价
- **WHEN** 用户在 active `pricing.yaml` 把 `jina.search` 单价改为 0.999
- **THEN** 下一次 run 的 cost_estimate_usd 反映新单价

#### Scenario: 单价缺失
- **WHEN** backend 'brave' 在 pricing.yaml 中无配置，被调用
- **THEN** 该条 jsonl 记录 `cost_estimate_usd: null`、`pricing_source: "unknown"`；usage-summary 末尾标「⚠️ brave:search 等单价未知，未计入合计」

### Requirement: 独立查询入口 usage.py 不进 context
plugin MUST 提供 `scripts/usage.py` 作为独立 CLI 查询入口。用户用 `!` 前缀执行（如 `! python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/usage.py --last 10`），输出落在用户终端，**MUST NOT** 进入任何 agent 的 context。主 agent **MUST NOT** 主动调用 usage.py。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-21

#### Scenario: 用户主动跑
- **WHEN** 用户在 Claude Code 输入 `! python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/usage.py --last 5`
- **THEN** 输出列出最近 5 次 run 的 cost；输出**不**进入主 agent 的 context（用户终端直出）

#### Scenario: 主 agent 不主动调
- **WHEN** 用户在对话中说「我想看历史」
- **THEN** 主 agent 提示用户跑 `! python3 .../usage.py --last 10`，**不**自己用 Bash 跑该命令

### Requirement: 业务代码不允许绕过 _http.py 自行打点
所有 backend 调用 MUST 经 `lib/_http.py` 出口；业务代码 MUST NOT 自行写 `usage.jsonl`。打点 schema 由 `lib/usage.py:record(...)` 统一负责。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-21

#### Scenario: 新 backend 添加
- **WHEN** 加一个新 backend 模块
- **THEN** 该模块的 HTTP 请求通过 `lib/_http.py:request_json` / `request_text`；打点自动产生，不需要 backend 代码手写

### Requirement: usage-summary.md 末尾追加「搜索摘要」段
`finalize_usage.py` 在生成 `<run_root>/usage-summary.md` 时 MUST 在文件末尾追加 `## 搜索摘要` 段，每行格式 `网站：<site> | 查询词：<term1>；<term2> | 次数：<n>`。被站点调用上限拦下的调用 MUST 单独写一行 `已跳过：<site>，原因：触发站点调用上限`。该段 MUST 含本次 run 所有真实发出的调用，含被拦下的尝试。搜索摘要 MUST 只写进 usage-summary.md（与 CLI `--show-queries`），MUST NOT 要求主 agent 把这段贴进给用户的最终回复（保留「仅一行 cost 总览」的克制设计）。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-26

#### Scenario: 一次完整调研
- **WHEN** 主 agent 跑完调研并调用 `finalize_usage.py <run_root>`
- **THEN** `<run_root>/usage-summary.md` 末尾存在 `## 搜索摘要` 段，每条调用 / 跳过一行

#### Scenario: 用户 CLI 看摘要
- **WHEN** 用户跑 `! python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/usage.py --last 1 --show-queries`
- **THEN** CLI 输出含最近一次 run 的「搜索摘要」段；输出不进入 agent context

### Requirement: 站点调用上限：同 run 同站点调用次数硬限
`lib/_http.py` 出口 MUST 维护一份进程内 `{(run_id, site): count}` 计数器；任何请求发出前 MUST 先查计数；达到上限的请求 MUST NOT 真正发出，MUST 由 `_http.py` 直接 raise `BackendError(retryable=False, reason="call_cap_exceeded")` 由上层捕获并落 fallback marker。上限值 MUST 可由 `~/.config/search-crew/limits.yaml` 的 `call_cap.ai_backend` / `call_cap.non_ai_backend` 覆盖，默认 AI backend 1 次、非 AI backend 2 次。

**上限只约束「搜索源」调用**（jina-search / serper / grok / gemini / doubao / 站点搜索 adapter）——目的是防 subagent 反复追打同一搜索源。**页面读取 / 抓取类操作 MUST 豁免本上限**（jina-reader、`fetch.py` 的直连探测）：读取已知 URL 是正常多次操作（如 fast-search「抓 top N」、deep-search 多页深挖），不应被计数拦截。豁免通过 `_http` 调用侧显式标记（如 `cap_exempt=True`）实现。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-26

#### Scenario: AI backend 默认 1 次
- **WHEN** 同 run 内对 grok 已成功调用 1 次后再次发起
- **THEN** 第 2 次请求被 `_http.py` 拦下，不真正发出 HTTP；调用方收到 `call_cap_exceeded` 错误

#### Scenario: 非 AI 搜索源默认 2 次
- **WHEN** 同 run 内对 jina-search 已调用 2 次后再次发起
- **THEN** 第 3 次请求被拦下

#### Scenario: 页面抓取豁免上限
- **WHEN** 同 run 内用 `fetch.py` / jina-reader 抓 5 个不同 URL（标记 cap_exempt）
- **THEN** 5 次抓取**全部放行**，不被站点调用上限拦截（上限只管搜索源）

#### Scenario: 用户改 limits.yaml 覆盖默认
- **WHEN** 用户在 active `limits.yaml` 设 `call_cap.ai_backend: 2`
- **THEN** AI backend 同 run 上限变为 2 次，第 3 次才被拦

#### Scenario: HTTP 429 retry 不增计数
- **WHEN** `_http.py` 内部对一次请求做 retry（HTTP 429 / 5xx）
- **THEN** 整次调用只计 1 次，retry 不重复计数

#### Scenario: 跨 run 不互通
- **WHEN** run-A 结束后开始 run-B
- **THEN** run-B 的计数器为空，与 run-A 完全独立

### Requirement: 新增 AI backend 走统一 _http.py 出口与 usage 打点
新增的 grok / gemini / doubao backend MUST 通过 `lib/_http.py:request_json` 发请求，由 `_http.py` 自动调 `lib/usage.py:record(...)` 打点。MUST NOT 在 backend 模块内绕过 `_http.py` 自行 `urllib.request.urlopen`。

#### Scenario: grok backend 调用打点
- **WHEN** fast-search 调 `ai_grok.search(query)`
- **THEN** `~/.local/state/search-crew/calls.jsonl` 新增一条 `backend: "grok", endpoint: "responses"` 记录

#### Scenario: cost 缺失时 cost_estimate_usd 为 null
- **WHEN** 三家 AI backend 在 `pricing.yaml` 中无单价配置
- **THEN** 对应 jsonl 记录 `cost_estimate_usd: null`、`pricing_source: "unknown"`；usage-summary 末尾标「⚠️ grok / gemini / doubao 单价未知，未计入合计」


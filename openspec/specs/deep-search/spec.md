# Deep Search

跨多轮深度调研。派 evidence-search / site-search 干活，自抓深挖允许，最终消化压缩成 HTML + Markdown 双格式报告。

## Purpose

把"调研一个领域 / verify 一个说法 / 全面对比"这类需要循环判断的复杂任务从主对话隔离出去；deep-search 自己规划、综合、判断、跟进。
## Requirements
### Requirement: deep-search 派活优先，自抓允许，不重新实现 backend
deep-search MUST NOT 自己拼 Jina / Serper 等 backend 请求，MUST NOT 在 synth 模式下尝试 Task 派发 worker（harness 不允许）。plan 模式下负责规划并输出紧凑 JSON；synth 模式下负责从 traces/ 自发现产物、综合、产出报告。自抓（fetch.py 直连已知 URL）仍允许。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-29

#### Scenario: plan 模式输出紧凑 JSON
- **WHEN** Task(deep-search, mode=plan, topic=...) 被调用
- **THEN** deep-search 输出形如 `{"tasks":[{"id":"T1","title":"...","query_en":"...","query_zh":"..."},...]}` 的 JSON，同时写 plan.md

#### Scenario: synth 模式自发现 traces
- **WHEN** Task(deep-search, mode=synth, run_root=...) 被调用
- **THEN** 通过 ls <run_root>/deep-search/traces/ 发现 worker 产物目录，读 INDEX.md，按需深入，产出 report.md + report.html，返回两个路径字符串

#### Scenario: 禁止 synth 模式 Task 派发
- **WHEN** deep-search synth 模式需要更多数据
- **THEN** 直接自抓（fetch.py）或用已有 traces；MUST NOT 尝试 Task(evidence-search)——harness 会失败

### Requirement: deep-search 第一轮产出 plan.md
deep-search 第一轮 MUST 先把 topic 拆成研究计划：角度 + 子任务清单 + 每子任务的完成判据，写入 `<run_root>/deep-search/plan.md`。后续每轮基于 plan 推进；每轮末尾对 plan 中的子任务自评 done / not-done。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-21

#### Scenario: 第一轮规划
- **WHEN** deep-search 收到 topic
- **THEN** 第一轮产出 `plan.md`，含至少一个角度 + 子任务清单 + 每子任务的完成判据

#### Scenario: 每轮自评
- **WHEN** deep-search 完成第 N 轮
- **THEN** 写 `round-N.md`，含本轮派发了什么、收回什么、对 plan 中每子任务的 done / not-done 自评

### Requirement: deep-search 同 turn 并行派发
deep-search 在一轮内派多个 subagent 时 MUST 在同一 message 内一次性发起多个 Task 工具调用（并行），不是串行。派发前 MUST 先调 `TaskCreate` 注册任务。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-28

#### Scenario: 一轮派 3 个 evidence-search
- **WHEN** deep-search 第一轮要并行调研 3 个子主题
- **THEN** 3 个 Task 工具调用在同一 message 内发起；TaskCreate 已先注册 3 个任务

### Requirement: deep-search 派 subagent 时传 target 目录
deep-search 派下级 subagent 时 MUST 把目标目录传给下级（如 `<run_root>/deep-search/traces/evidence-search-<sid>/`），让下级在该目录内工作。这避免「一次 deep-search 的产物散落在多个 session-id 目录」。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-28

#### Scenario: 派 evidence-search 时传 target_dir
- **WHEN** deep-search 派 evidence-search
- **THEN** 调用参数包含 `target_dir=<run_root>/deep-search/traces/evidence-search-<sid>/`；下级产物落在该目录而非自己的 session-id 目录

### Requirement: deep-search 主交付物 = report.html + report.md 双格式
deep-search 综合阶段 MUST 同时产出 `<run_root>/deep-search/report.html`（给用户，LLM 自由生成的可视化形态）+ `<run_root>/deep-search/report.md`（给主模型，纯 markdown）。两份文件 MUST 语义等价——不允许 HTML 多结论 / 少结论。HTML 中的循证链接 MUST 可点击，链接对象为外部 URL 或本地 markdown 路径。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-21

#### Scenario: 综合阶段产出双格式
- **WHEN** deep-search 完成所有子任务，进入综合阶段
- **THEN** 产物目录下同时存在 `report.html` 与 `report.md`，两者陈述的结论 / 引用相同

#### Scenario: 用户优先看 HTML，主模型优先看 markdown
- **WHEN** 主 agent 收到 deep-search 返回
- **THEN** 主 agent Read `report.md`（不读 HTML，效率太低）；告知用户用 `open report.html` 直观查看

### Requirement: deep-search 保留可追溯的底层产物
deep-search 综合阶段 MUST 丢弃绝大部分原始内容、给报告，但 MUST 保留可追溯的底层产物子目录（`<run_root>/deep-search/traces/`），让上级或用户想验证时可以下钻。报告中的引用 anchor 指向 traces 内的具体 markdown 段落。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-21

#### Scenario: traces 保留
- **WHEN** deep-search 完成综合
- **THEN** `<run_root>/deep-search/traces/` 下保留所有派出的 evidence-search / site-search 的完整产物

#### Scenario: 报告引用回 traces
- **WHEN** `report.md` 中陈述一个结论
- **THEN** 结论后跟 `见 [evidence-search-003 §<slug>](traces/evidence-search-<sid>/evidence-search-003.md#<slug>)` 风格的引用

### Requirement: deep-search max_rounds 硬上限
deep-search MUST 受 `~/.config/search-crew/limits.yaml` 的 `deep_search.max_rounds` 限制（默认 5）。即便子任务未完成，达到上限 MUST 进入综合阶段并在报告中显式标注未完成项。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-21

#### Scenario: 达到 max_rounds
- **WHEN** deep-search 跑到第 5 轮仍有未完成子任务
- **THEN** 进入综合阶段；report 中显式标注哪些子任务未完成、为什么未完成

### Requirement: deep-search 触发反例（不应派 deep-search 的场景）
deep-search agent description 中 MUST 包含「不要因以下情况派 deep-search」反例清单。反例 MUST 至少覆盖：单轮信息已够、单条事实查询、用户只问一句概念、明确指定唯一站点（应派 site-search）。

#### Scenario: 主 agent 看到反例后不误派
- **WHEN** 用户说「React 19 引入了什么新 hook」
- **THEN** 主 agent 根据反例「单条事实查询」判断，不派 deep-search，改派 evidence-search 或 site-search

#### Scenario: agent description 含反例段
- **WHEN** 读取 `agents/deep-search.md`
- **THEN** 文件存在标题为「## 不要触发本 agent 的场景」的反例清单段

### Requirement: deep-search plan.md 中子任务查询词遵循「主题 + 目标 + 限定条件」
deep-search 在第一轮 plan.md 中写出每个子任务的预期查询词时 MUST 至少含「主题 + 目标 + 限定条件」三要素。MUST NOT 把子任务查询词写成单个名词。限定条件 MUST 覆盖至少一项：语言、地区、时间范围、平台范围、输出形式。

#### Scenario: plan.md 子任务查询词含三要素
- **WHEN** deep-search 第一轮写 `plan.md`，含三个子任务
- **THEN** 每个子任务的预期查询词字段都不只是单名词，至少含主题 + 目标 + 一项限定条件

#### Scenario: 派 evidence-search 时透传完整查询词
- **WHEN** deep-search 派出 evidence-search 跑某子任务
- **THEN** 传给 evidence-search 的 query 与 plan.md 中记录的预期查询词一致（含三要素）

### Requirement: deep-search 按复杂度缩放投入（在 caps 内）
deep-search 第一轮规划时 MUST 在 `plan.md` 顶部显式记一行**复杂度评估 + 投入决策**（用几个 worker、预计几轮），并据此选用 worker 数与轮数。worker 数 MUST ≤ `~/.config/search-crew/limits.yaml` 的 `deep_search.per_round_breadth`（该值语义为**每轮上限**，非固定值）；轮数 MUST ≤ `deep_search.max_rounds`。简单题 MUST 用更少 worker / 更少轮（不铺满）；复杂题才铺满。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-28

#### Scenario: plan.md 含复杂度评估与投入决策
- **WHEN** deep-search 收到 topic 产出 plan.md
- **THEN** plan.md 顶部含一行形如「复杂度：中等 / 本轮 3 个 worker / 预计 2 轮」的评估，且实际 worker 数 ≤ per_round_breadth、轮数 ≤ max_rounds

#### Scenario: 简单题不铺满
- **WHEN** topic 较简单（单一主题中等深度）
- **THEN** deep-search 用 1-3 个 worker、1-2 轮即收，不必用满 per_round_breadth 或跑到 max_rounds

### Requirement: deep-search 把本次假设的调研范围写进 plan.md
deep-search MUST 在 `plan.md` 顶部写明**本次假设的调研范围 / 角度**（如「本次按 X 范围调研，如需调整请说」），使范围始终可见、可被上级或用户中途纠偏。（开跑前的主动澄清由主 agent 在派发前做，见 orchestration capability。）

#### Scenario: plan.md 顶部声明假设范围
- **WHEN** deep-search 收到 topic 产出 plan.md
- **THEN** plan.md 顶部含一段「本次假设范围 / 角度」声明

### Requirement: deep-search 派 worker 时给出任务契约四要素
deep-search 派 evidence/site-search 时，Task prompt MUST 含四要素，缺任一视为缺陷：①目标（要回答的子问题）②输出格式（产物形态，按既有产物约定）③工具/源指引（起点路由 + routing 硬规则）④边界（不越界到别的子任务、不多轮、命中权威主题回信号）。

#### Scenario: 派发 prompt 四要素齐全
- **WHEN** deep-search 派一个 evidence-search 跑某子任务
- **THEN** 该 Task 调用的 prompt 含明确的 目标 / 输出格式 / 工具源指引 / 边界 四部分

### Requirement: deep-search 综合阶段显式标注源间矛盾与循证状态
deep-search 综合 report.md / report.html 时，跨多源得到的结论若存在**冲突 / 分歧**，MUST 显式标出（指明哪个源说什么），MUST NOT 偷偷只选一个而不提分歧。每条关键结论 MUST 标注循证状态：已回官方源复核 / 未复核存疑（沿用循证四步第 4 步）。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-28

#### Scenario: 多源分歧被标出
- **WHEN** 两个来源对同一指标给出冲突数据
- **THEN** 报告显式呈现「⚠️ 分歧：源 A=X，源 B=Y」，而非只取其一

#### Scenario: 结论标循证状态
- **WHEN** 报告陈述一条来自非官方源的关键结论
- **THEN** 该结论标注「未在官方源验证」或「已复核」

### Requirement: deep-search 每轮做显式 gap 评估再决定下一步
deep-search 每轮写 `round-N.md` 时，除「派了什么 / 收了什么 / 子任务 done 自评」外，MUST 加一段显式 gap 评估：已覆盖什么、还缺什么、下一轮补哪个角度（或判定已够、进入综合）。该评估 MUST 作为「继续派下一轮 vs 收敛」的依据。

#### Scenario: round-N.md 含 gap 评估
- **WHEN** deep-search 完成第 N 轮
- **THEN** round-N.md 含「已覆盖 / 还缺 / 下一轮补哪个角度（或进入综合）」段，且下一步决策与该评估一致


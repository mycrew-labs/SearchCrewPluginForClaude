## MODIFIED Requirements

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

## MODIFIED Requirements

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

## MODIFIED Requirements

### Requirement: deep-search 派活优先，自抓允许，不重新实现 backend
deep-search MUST NOT 自己拼 Jina / Serper 等 backend 请求。所有通用搜索 MUST 通过派 evidence-search 完成，所有官方站精确搜索 MUST 通过派 site-search 完成。但 deep-search **被允许**直接用 `fetch.py` 抓已知 URL，或沿页面链接深挖。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-28

#### Scenario: 派 evidence-search 做通用调研
- **WHEN** deep-search 第一轮需要广度调研某子主题
- **THEN** 派出 evidence-search subagent，不自己调 `search.py`

#### Scenario: 自抓已知 URL
- **WHEN** deep-search 在第二轮拿到一个具体 URL 想深挖
- **THEN** 允许直接调 `fetch.py <url>`，无需多派一个 subagent

#### Scenario: 禁止自拼 backend 请求
- **WHEN** deep-search 想做一次通用搜索
- **THEN** MUST 派 evidence-search；不允许自己直接 HTTP 调 Jina / Serper

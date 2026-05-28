## Context

现 `fast-search` 把「快出答案」和「结构化循证采集」揉一起，~3min（haiku 把 17 万字重写成 5 个文件）。拆分：`/search-fast` = AI 综述快答（主 agent 直连、无 subagent）；结构化采集降为 `evidence-search`（deep/wide 的廉价工人）。

依赖：bocha backend（change A，已并入 main）、fetch opencli-remote 层（change B，已并入）。

## Goals / Non-Goals

**Goals:**
- `/search-fast` 秒级出 AI 综述 + citations，无 subagent、无结构化产物。
- `evidence-search` = 原 fast-search 行为 + **中英双语并发**（serper 全球 + bocha 中文并行，merge）；serper 主 jina 备，全挂回落 Claude WebSearch。
- deep/wide 改派 evidence-search。
- 能力 spec 重组：fast-search 6 条 worker 锁需求迁 evidence-search；fast-search 转为快答语义。

**Non-Goals:**
- 不改 deep/wide 对外行为（只换内部 worker 名）。
- 不做 AI 综述的多源并行（快答只一个 AI 源，按语言选）。

## Decisions

### D1：`/search-fast` = 主 agent 直连 `ai_search.py`（无 subagent）
- 新脚本 `ai_search.py`：按语言/语境选一个 AI 综述源（中文→doubao、全球英文→gemini、X/实时→grok；沿用 routing.yaml selection_order），一次调用，输出 `{backend, summary, citations}`。
- AI 选择 / 调用逻辑从 `search.py` 抽到 `lib/ai_summary.py`，`search.py --prefer ai` 与 `ai_search.py` 共用，避免重复。
- `commands/search-fast.md` 重写：主 agent 造 run 目录 → 跑 `ai_search.py` → 呈现 summary + citations + 一行 cost。不派 subagent。

### D2：`fast-search` subagent → 重命名 `evidence-search`
- `agents/fast-search.md` → `agents/evidence-search.md`，frontmatter `name: evidence-search`，model 仍 haiku。
- 行为保留：jina `--with-content` 一次带正文、ranking + 推荐 + 关键词、产物前缀、零 key 回落、不站内/不多轮、查询词构造。
- **新增中英双语并发**：对一个查询，生成 EN + ZH 两版，**同 turn 并发**跑两条 lane：
  - 全球/权威 lane：`search.py --prefer serper`（EN）；serper 失败 → jina（jina 可 `--with-content`）。
  - 中文 lane：`search.py --prefer bocha`（ZH）。
  - 两 lane 结果 merge + 去重（按 URL）。两 lane 都挂 → Claude WebSearch 兜底。
  - serper/bocha 给 snippet/summary、无全文 → 对需要全文的 top 结果用 `fetch.py` 并发补抓；jina lane 已带 content 免抓。

### D3：deep/wide 改派 evidence-search
deep-search.md / wide-search.md 中「派 fast-search」全改「派 evidence-search」（subagent_type、SEARCH_CREW_SUBAGENT 值、文案）。

### D4：能力 spec 重组
- `fast-search` 能力：REMOVE 6 条 worker 锁需求；ADD「/search-fast = AI 综述快答（主 agent 直连、无 subagent、无结构化产物）」。
- `evidence-search` 能力（NEW）：迁入 6 条 worker 需求（重新落锁）+「中英双语并发 + serper 主 jina 备 + WebSearch 兜底」。
- `orchestration`：MODIFY `/search-fast` 语义；deep/wide 派 evidence-search。

## Risks / Trade-offs

- **blast radius 大**：重命名 locked 能力 + 6 条锁迁移 + /search-fast 语义改 + 文件改名 + deep/wide 引用。靠测试 + 锁确认 gate 兜。
- **双语并发的 token / 成本**：evidence-search 一次跑两 lane（serper+bocha）+ 补抓，比单 lane 贵——但它是 deep/wide 的工人、本就该全面；call_cap 仍按 backend 限。
- **`/search-fast` 产物语义变了**：从"5 个证据文件"变"一段综述+citations"。这是有意变更，README 写明。
- **AI 综述快答的循证弱**：综述非原文。要原文证据请用 deep（内部走 evidence-search）。

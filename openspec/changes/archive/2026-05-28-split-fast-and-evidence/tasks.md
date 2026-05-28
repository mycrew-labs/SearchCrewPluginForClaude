## 1. AI 综述快答（/search-fast 直连）

- [x] 1.1 抽 `lib/ai_summary.py`：把 search.py 的 _pick_ai_backend / _resolve_tier / _resolve_model / _run_ai 迁过来，search.py 改 import 复用
- [x] 1.2 新建 `ai_search.py`：按语言/语境选 AI 源（doubao/grok/gemini）一次综述，输出 `{backend, summary, citations}`；命中硬规则则提示走 site/deep；全缺 key 回落非 AI
- [x] 1.3 重写 `commands/search-fast.md`：主 agent 造 run 目录 → 跑 ai_search.py → 呈现综述+citations+一行 cost，不派 subagent

## 2. evidence-search（原 fast-search 重命名 + 双语并发）

- [x] 2.1 `agents/fast-search.md` → `agents/evidence-search.md`：frontmatter name=evidence-search、描述改循证采集工；产物前缀 evidence-search
- [x] 2.2 加中英双语并发 lane：serper(EN) + bocha(ZH) 同 turn 并发，serper 失败回落 jina，两挂回落 WebSearch；merge 去重；缺正文 top 结果并发 fetch
- [x] 2.3 触发反例段补「只想要一口答案→/search-fast」

## 3. deep/wide 改派 evidence-search

- [x] 3.1 `agents/deep-search.md`：所有「派 fast-search」→「派 evidence-search」（subagent_type / SEARCH_CREW_SUBAGENT / 文案 / 任务契约示例）
- [x] 3.2 `agents/wide-search.md`：worker 复用「fast-search」→「evidence-search」

## 4. 文档

- [x] 4.1 README 三层入口表 + 历史；SKILL.md 增 ai_search.py、evidence-search 说明
- [x] 4.2 `tests/MANUAL.md`：/search-fast 直连出综述无 subagent；evidence-search 双语并发 + serper 主 jina 备；deep/wide 派 evidence-search

## 5. 测试

- [x] 5.1 `ai_search.py` 单测：选源（语言）、输出结构、全缺 key 回落
- [x] 5.2 `lib/ai_summary` 抽离后 search.py --prefer ai 仍工作（回归）
- [x] 5.3 全量 `unittest discover` 通过

## 6. 归档前：锁确认 gate（blast radius 大，逐条过）

- [x] 6.1 `openspec validate split-fast-and-evidence --strict` 通过
- [ ] 6.2 完工简报：列出受影响的全部 locked 需求——fast-search REMOVE 6 锁、evidence-search 迁入重锁 4 条 + 新「/search-fast 快答」锁、orchestration MODIFY 2 锁、deep-search MODIFY 1 锁、wide-search MODIFY 1 锁；逐条请用户确认
- [ ] 6.3 用户确认 → bump version → `openspec archive` → commit → push
- [ ] 6.4 **manual** reload 后实测：/search-fast 秒级出综述无 subagent；/search-deep 内部派 evidence-search；evidence-search 双语并发

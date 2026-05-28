## 1. 配置 + ai_search

- [x] 1.1 `defaults/routing.yaml`：`ai_summary` 加 `fast_default: auto` + 注释（auto/grok/gemini/doubao）
- [x] 1.2 `ai_search.py`：读 `ai_summary.fast_default`；具体家且可用→强制；auto/缺失/不可用→回落现有语言逻辑

## 2. seed --set-fast-default

- [x] 2.1 `seed_user_config.py --set-fast-default <auto|grok|gemini|doubao>`：在 active routing.yaml 的 `ai_summary:` 块内 set/insert `fast_default:` 行；记 changelog（op=seed/set-fast-default，trigger 默认 setup）；值非法则报错

## 3. setup

- [x] 3.1 `commands/search-skill-setup.md`：加「选快答默认引擎」环节——AskUserQuestion（auto / 都用 gemini / 都用 doubao / 都用 grok）→ AI 跑 `--set-fast-default <choice>`（不手改 active）

## 4. 测试

- [x] 4.1 `ai_search` 单测：fast_default=具体家→强制；auto→语言逻辑；不可用→回落
- [x] 4.2 `--set-fast-default` 单测：写入 ai_summary.fast_default、幂等改值、非法值报错、记 changelog
- [x] 4.3 全量 unittest

## 5. 验证 + 归档

- [x] 5.1 `openspec validate fast-default-engine --strict`
- [x] 5.2 完工简报：MODIFY config-lifecycle「seed」locked（扩 init 配置写入）、ADD fast-search 一条；确认 → bump → archive → commit → push
- [ ] 5.3 **manual** reload 实测：setup 选 gemini 后中文 query 也走 gemini；选 auto 中文回 doubao

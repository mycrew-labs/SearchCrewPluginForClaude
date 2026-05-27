## 0. 前置 bugfix：调用上限豁免读取操作（用户选 B）

- [x] 0.1 `lib/_http.py`：`request_json` / `request_text` 加 `cap_exempt: bool = False`；`_check_and_increment_cap` 在 exempt 时直接 return（不计数、不拦截）
- [x] 0.2 `lib/jina.py` 的 `fetch`（jina-reader）传 `cap_exempt=True`；`search` 保持计数（默认）
- [x] 0.3 `tests/test_call_cap.py` 加用例：cap_exempt=True 连续多次不被拦；search 仍受限

## 1. fetch.py 改造（raw + 反爬识别）

- [x] 1.1 `lib/_http.py` 加一个返回 `(text, content_type)` 的取法（`request_text_meta`，传 `cap_exempt=True`），供 fetch.py 直连探测 Content-Type
- [x] 1.2 `fetch.py` 改为：先直连 GET 拿 body + Content-Type（经 `_http`，保留 call-cap + usage 打点）
- [x] 1.3 反爬识别：抽一个 `_looks_blocked(text) -> bool`（双条件：短内容 < 1500 字 + 命中签名 `环境异常`/`完成验证后即可继续访问`/`去验证`/`requiring CAPTCHA`/`拖动下方滑块`/`滑块`/`captcha`，大小写不敏感）；命中 → 输出 `{source: null, markdown: null, blocked: "anti_bot", fallback: null}`
- [x] 1.4 Content-Type 判定：`text/html`/`application/xhtml+xml` → 二次送 `jina.fetch` 渲染（`source: jina-reader`）；`text/plain`/`text/markdown`/`application/json`/其他 `text/*`/源码类/`application/xml` → 原文直返（`source: raw`）
- [x] 1.5 兜底：Content-Type 缺失/含糊（`application/octet-stream` 等）→ 看 body 有无 HTML 标签（`<!doctype html`/`<html`/`<head`/`<body`）；无 → raw，有 → Jina
- [x] 1.6 Jina 渲染后的内容也跑一遍 `_looks_blocked`（微信经 Jina 也是验证页）
- [x] 1.7 更新 fetch.py docstring 的输出契约（新增 source:"raw" / blocked:"anti_bot"）

## 2. web-page-fetch skill

- [x] 2.1 新增 `skills/web-page-fetch/SKILL.md`：description 写明「用户给 URL 要读/总结/抽取内容时，主 agent 优先用本 skill（调 fetch.py）而非内置 WebFetch」
- [x] 2.2 SKILL.md 写三态分派：source 非 null → 用 markdown；`WEBFETCH_FALLBACK` → 内置 WebFetch；`blocked: anti_bot` → 诚实报「被风控/验证码拦截」，禁止解验证码
- [x] 2.3 SKILL.md 标注已知不支持：微信公众号 `mp.weixin.qq.com`（风控 + 滑块）；非验证码的 SPA/登录墙可建议 browser-control 升级
- [x] 2.4 SKILL.md 顶部声明「fetch backend 是当前实现（Jina Reader + 直连），不是身份」（与现有两个 SKILL 一致），为 B-006（OpenCLI 进阶后端）留口

## 3. 命令改名

- [x] 3.1 `commands/setup.md` → `commands/search-skill-setup.md`，frontmatter `name: search-skill-setup`；正文内 `/setup` 自引用改 `/search-skill-setup`
- [x] 3.2 `commands/deep-search.md` → `commands/search-deep.md`，frontmatter `name: search-deep`；正文「派 deep-search subagent」等 subagent 引用**不动**，仅命令自引用 `/deep-search` → `/search-deep`
- [x] 3.3 确认不动：subagent 名（agents/*.md）、`<run_root>/deep-search/` 路径、`SEARCH_CREW_SUBAGENT` 值、产物前缀

## 4. 文档同步

- [x] 4.1 `README.md`：安装段 `/setup` → `/search-skill-setup`；触发表 `/deep-search` → `/search-deep`；新增 web-page-fetch skill 一句话介绍
- [x] 4.2 `tests/MANUAL.md`：`/setup`、`/deep-search` 命令调用 → 新名（**不动**路径引用）
- [x] 4.3 `commands/search-deep.md` / `commands/search-skill-setup.md` 内对彼此的引用更新
- [x] 4.4 `EXTENDING.md`：新增「web-page-fetch skill 如何增强」小节（提 raw/反爬/B-006 OpenCLI 方向）
- [x] 4.5 `skills/search-toolkit/SKILL.md`：fetch.py 输出契约段补 raw/blocked 两态

## 5. 测试

- [x] 5.1 `tests/test_fetch_raw.py`：mock 直连响应，验证 Content-Type=text/plain → source:raw 原文直返；text/html → 走 jina 分支
- [x] 5.2 `tests/test_fetch_antibot.py`：mock 含「环境异常/去验证」的短内容 → blocked:anti_bot；含「captcha」的长正文 → 不误判
- [x] 5.3 兜底分支测试：无 Content-Type + 无 HTML 标签 → raw；有 HTML 标签 → jina
- [x] 5.4 全量 `python3 -m unittest discover -s tests -t .` 通过

## 6. 归档前：锁确认 gate（按 change-flow 新规则）

- [x] 6.1 `openspec validate public-fetch-and-command-rename --strict` 通过
- [x] 6.2 **完工简报**给用户：拟加锁清单（web-page-fetch 的反爬识别 / 三态分派等候选）+ 2 处 locked 编辑（orchestration RENAMED+MODIFIED、config-lifecycle MODIFIED）逐条确认
- [x] 6.3 用户确认 → 落锁 / 保留锁 → `openspec archive public-fetch-and-command-rename`
- [ ] 6.4 **manual** · 装插件后实测：`/search-skill-setup` 能跑、`/search-deep` 能跑、主 agent 读普通 URL 走 fetch.py、读 raw.githubusercontent README 得原文、读微信得 anti_bot 诚实失败

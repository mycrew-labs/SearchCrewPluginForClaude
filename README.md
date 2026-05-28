# Search Crew

Claude Code plugin。为调研类任务提供分层能力：日常关键词触发的快速搜索、官方站点的精确搜索、跨多轮的深度循环调研。所有搜索结果通过文件系统中介隔离 context，主对话窗口干净。

> Search Crew 是 **MyCrew** 旗下首个 plugin。
>
> - GitHub org：<https://github.com/mycrew-labs>
> - Docker Hub namespace：<https://hub.docker.com/repositories/mycrew>

## Vision

这虽然是一个搜索工具，但**如何让用户理解数据的关联关系**、**如何真正把循证传递下去**，才是它优化的方向。

具体落成三个长期主轴：

1. **数据关联关系**——产物目录组织、ranking、关键词索引、wiki 风格大纲、附件去重，让主模型和用户能像浏览一个陌生但结构清晰的代码库一样自助导航。
2. **循证传递**——搜索过程严格循证（先官方源 → 扩展 → 关键结论回官方源复核），结论使用阶段强制保留原始证据（URL、原文摘录、关键数字）。
3. **自我进化**（长期）——把 [karpathy/autoresearch](https://github.com/karpathy/autoresearch) 的 checklist 评分 + 山爬迭代引入站点适配器与查询策略的自动优化，让 plugin 越用越好。

## 阶段路线图

- **第一阶段（当前 change `init-search-crew`）**：把三个 subagent、循证工作流、产物组织约定、配置生命周期、Stop hook 学习闭环落到位
- **第二阶段（后续 change）**：实现 autoresearch 式适配器自动优化，让"自我进化"从设想落到工程

## 治理

所有重大设计、行为约定、产品意志走 [OpenSpec](./openspec/) 流程：

- [`openspec/project.md`](./openspec/project.md) ：项目简介 + Backlog
- `openspec/USER_DESIGN.md` ：项目级产品行为台账（待 `init-search-crew` 归档后生成）
- `openspec/TECH.md` ：项目级技术决策台账（待生成）
- [`openspec/changes/`](./openspec/changes/) ：进行中的变更

## 安装

```bash
/plugin marketplace add mycrew-labs/SearchCrewPluginForClaude    # 从 GitHub
# 或：/plugin marketplace add /path/to/SearchCrewPluginForClaude  # 从本地 checkout
/plugin install search-crew@search-crew            # 插件名@marketplace名（都是 search-crew）
/reload-plugins                                    # 重载使插件生效（或重启 Claude Code）
/search-skill-setup                                # 检查 backend / Chrome / 引导
```

> 插件命令带命名空间：`/search-skill-setup`、`/search-deep`、`/search-wide`、`/search-fast`（完整形式 `/search-crew:...`）。命令名用 `search-*` 前缀，不占用通用全局名。

可选 API key（不配置也能用）：复制 `.env.example` 到 `~/.zshrc` 填入。

支持的 backend：

- 通用搜索：`JINA_API_KEY`（语义）/ `SERPER_API_KEY`（Google 关键词）
- AI 综述（任选一个或多个，全未配自动回落 jina）：
  - `GROK_API_KEY`（grok / xAI，偏英文舆论 / 实时讨论）
  - `DOUBAO_API_KEY`（doubao / 火山方舟，托管 Doubao / DeepSeek 等，偏中文语境）
  - `GEMINI_API_KEY`（gemini / Google Search Grounding，偏全球综述）
- 站点适配器：`GITHUB_TOKEN`（可选，提高 API rate limit）

用哪个 model 在 `~/.config/search-crew/routing.yaml` 的 `ai_summary.models` 里按 fast/deep 分层配置（不在 env 写 model）。详见 `.env.example` 与 [EXTENDING.md「AI 综述 backend」](./EXTENDING.md#0-ai-综述-backendgrok--gemini--doubao)。

## 更新插件

本插件通过第三方 marketplace 分发，**默认不自动更新**。仓库有新版本后，在 Claude Code 里：

```bash
/plugin marketplace update search-crew    # 从 GitHub 重新拉取最新 marketplace
/reload-plugins                           # 生效（或重启 Claude Code）
```

想自动更新：`/plugin` → **Marketplaces** 标签页 → 选 search-crew → **Enable auto-update**（开启后每次启动自动刷新 + 更新已安装插件，有更新会提示你 `/reload-plugins`）。

> ⚠️ **能不能收到更新，取决于维护方有没有 bump 版本号**——见下方「发布新版本」。

## 本仓库开发者：激活 git hook

clone 本仓库后跑一次（激活 OpenSpec 归档检查 pre-commit hook）：

```bash
git config core.hooksPath .githooks
```

hook 脚本在 `.githooks/pre-commit`（随仓库走，更新会随 `git pull` 到位）。激活后每次 commit 自动检查「有 change 实施完成但未归档」的情况。

## 发布新版本（维护方铁律）

> 🔴 **每次发布 MUST bump 版本号**，否则已安装用户**收不到更新**。

Claude Code 的规则：`plugin.json` 设了 `version` 时，用户**只在该字段被 bump 时**才收到更新（不 bump = 等于没发）。所以每次要让用户拿到的改动，发布前 MUST：

1. 同步 bump **两处** `version`：`.claude-plugin/plugin.json` 与 `.claude-plugin/marketplace.json`（保持一致）
2. 语义化版本（pre-1.0）：加功能 / 破坏性改动 → bump minor（0.x.0）；纯修 bug → bump patch（0.x.y）
3. commit + push 到 GitHub；用户按上方「更新插件」拉取

历史：`0.1.0` 初始 → `0.2.0`（grok/gemini/doubao AI 综述 + web-page-fetch + 命令改名 search-*）→ `0.2.1`（web-page-fetch 预留远程 browser-host 进阶配置槽 / B-006）→ `0.3.0`（deep-search 融入 deep research：按复杂度缩放 + 派发前澄清 + 任务契约四要素 + 找矛盾 + gap 评估）→ `0.4.0`（新增 wide-search 批量对照矩阵 + 暴露 /search-wide、/search-fast 命令）→ `0.4.1`（wide-search lead 改用 opus 以保上下文长度 + README 增三种调研形态对比）→ `0.5.0`（active 配置双通道写入：固定脚本操作 seed/merge/promote + changelog 留痕 + setup 自动检测缺段；禁 AI 手改 active）→ `0.5.1`（修 usage 打点 run_root 与产物目录分叉致 cost 报 0 的 bug：新增 run_paths.py，subagent 不再自己编 session_id；fast-search 产物体量与抓取克制以治慢）→ `0.5.2`（fetch.py 支持多 URL 并发抓取 `fetch.py <url1> <url2> ...`，fast-search 抓多条改并发）→ `0.5.3`（并发默认数 2→5：核实 Jina Reader 免费 key 是 500 RPM、并发非瓶颈，跟随生态惯例取 5，可调）→ `0.5.4`（finalize_usage `--one-line` 支持 `--subagent` 切片，/search-fast cost 行不再累计整会话）→ `0.5.5`（AI backend 回退非 AI 搜索时记 stderr 日志，不再静默）→ `0.5.6`（search.py 加 `--with-content`：jina 一次带回结果正文，fast-search 省掉逐页 fetch round-trip，端到端 ~10s→~2s）→ `0.6.0`（per-dispatch run 目录：每次 `/search-*` 造独立 run 目录、经 `SEARCH_CREW_RUN_ROOT` 沿派发链共享，cost/call-cap/产物按次隔离；反转 0.5.x 的会话级模型）→ `0.7.0`（新增 bocha 中文搜索 backend：`search.py --prefer bocha`，补中文短板，走统一 _http + 打点 + call-cap）→ `0.7.1`（fetch.py 抓取链加 opencli-remote 中间层：jina-reader → opencli-remote(B-006 预留，默认关) → Claude WebFetch；遇 needs_auth/反爬/jina 失败时若启用则走远程登录态浏览器）→ `0.8.0`（拆分 fast-search：`/search-fast` 改为 AI 综述快答（主 agent 直连 ai_search.py，无 subagent）；原结构化采集工重命名 evidence-search，中英双语并发 serper+bocha、deep/wide 改派它）。

## 三层入口

| 场景 | 触发方式 |
|---|---|
| AI 综述快答 | `/search-fast <主题>`：主 agent 直连 `ai_search.py`，一次 AI 调用出综述 + 引用，秒级、不派 subagent、不产文件。要现成答案用它 |
| 站内精确搜索 | 对话直接说「去 X 官网查...」自动派 site-search |
| 读取具体网页 / 文件 | 给出 URL 说「读一下 / 总结这个页面」自动用 web-page-fetch（优先于内置 WebFetch；HTML 渲染 + raw 原文 + 反爬识别） |
| 深度循环调研 | `/search-deep <主题>` 手动触发（内部派 evidence-search 采集证据） |
| 批量对照矩阵（求广） | `/search-wide <批量对比需求>` 手动触发；或说「对比这 N 个 ...」自动派 wide-search。每对象一个独立 evidence-search worker 并行，汇成可排序矩阵 |
| 结构化循证采集 | `evidence-search`（中英双语并发 + 抓正文 + ranking + INDEX）—— 不单独暴露命令，由 deep/wide 内部派发 |
| 查历史使用 | `! python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/usage.py --last 10` |
| 查最近搜了哪些词 | `! python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/usage.py --last 3 --show-queries` |

## 快答 / 深 / 广：四个角色怎么选

一句话判别：

> **要一口现成答案 → `/search-fast`（AI 综述）；把一个题挖透 → `/search-deep`；多个对象排成表 → `/search-wide`。** evidence-search 是 deep/wide 内部用的"采集工"，不直接面向用户。

### 打个比方

- **/search-fast（AI 综述快答）** 像**问一个读过全网的朋友**：直接给你一段嚼碎的答案 + 来源，秒级。主 agent 一次 AI 调用搞定，不派 subagent、不留文件。要"快点知道"用它。
- **evidence-search（采集工）** 像**派一个实习生跑图书馆**：中英双语并发搜一轮、抓回原文、打 ranking、写结构化索引。它不直接面向用户，是 deep/wide 的廉价工人。
- **/search-deep** 像**研究员带着实习生反复跑**：列计划 → 派 evidence-search 采证 → 评估缺口 → 再派 → 回官方源复核 → 写带证据、标分歧的报告。"这个题要彻底搞懂"用它。
- **/search-wide** 像**项目经理同时派 N 个实习生**：每对象一个 evidence-search worker 并行采集，汇成可排序对照矩阵。"把 N 个对象排成表"用它。

### 对照表

| 维度 | /search-fast | evidence-search | /search-deep | /search-wide |
|---|---|---|---|---|
| **给什么** | AI 综述 + 引用 | 结构化证据文件 + 索引 | 叙述式研究报告 | 可排序对照矩阵 |
| **面向** | 用户（直接） | deep/wide（内部工人） | 用户 | 用户 |
| **派 subagent?** | 否（主 agent 直连脚本） | 否（自己是 worker） | 派 evidence/site worker | 派 N 个 evidence/site worker |
| **跑几轮** | 一次 AI 调用 | 单轮（双语并发） | 多轮（≤5） | 单轮 N worker 并行 |
| **速度/成本** | 最快、最省 | 中（双语 + 抓正文） | 高（多轮 + opus） | 中高（N worker + opus 指挥） |

### evidence-search 是 deep/wide 的共享工人

`/search-fast` 走 AI 综述、不碰 evidence-search。而 deep 和 wide 自己**不直接搜**，把活拆开派给 evidence-search（或 site-search）——区别只在拆的方向：

- **deep = 纵向**：同一个题，一轮接一轮往深里挖。
- **wide = 横向**：N 个对象，一次性铺开同时查。

所以 wide-search 派很多 worker 也不至于太贵：**贵的旗舰模型只用在少数"指挥/汇总"角色上，真正跑腿的 N 个 worker 用便宜的快速档**。

## 扩展

见 [EXTENDING.md](./EXTENDING.md)：

- 新增通用搜索 backend（Brave / Tavily 等）
- 新增站点适配器（YAML 配置型 / Python 代码型，用户态零侵入）
- 修改路由起点 / cost 单价 / subagent 上限

## 状态

- ✅ 第一阶段（init-search-crew）：三个 subagent + skills + commands + defaults 全部就位
- 🚧 持续接入：B-001 ~ B-005 见 [project.md](./openspec/project.md)

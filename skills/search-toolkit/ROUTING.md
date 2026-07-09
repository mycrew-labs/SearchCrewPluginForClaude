# 循证路由起点表（基线 / 给 LLM 阅读用）

> 本文件是给 subagent 阅读的**人类可读基线**。实际 runtime 加载的程序化版本是
> `~/.config/search-crew/routing.yaml`（首次安装时从 `defaults/routing.yaml` 拷贝）。
> 用户可以自由改动 YAML 版本——本 markdown 仅作为 LLM 启动时的概念性参考。

整体逻辑 [USER_DESIGN P-ROUTE-001](../../openspec/changes/init-search-crew/USER_DESIGN.md)：

> 路由清单是**起点**而非终点。整体逻辑是严格的循证：
> 1. **先在起点搜**
> 2. **信息不足时扩展**
> 3. **关键结论必须回官方源复核**
> 4. **未通过复核的内容必须标注**

适用范围：**所有 subagent + 主 agent** 都遵循。

---

## AI 综述层（未命中硬规则时的第一跳）

query 未命中下方任一硬规则时，subagent **优先**调用一个 AI 综述 backend 作为「先建立假设」的入口，再决定是否补充 jina / serper / 站点搜索。

- **触发条件**：(1) `~/.config/search-crew/routing.yaml` 中 `ai_summary.enabled: true`；(2) query 未命中任一 `hard_rule: true` 的 topic；(3) `selection_order` 中至少一个 backend 的 key 已配
- **三家选源经验**（subagent 在 prompt 内按语言 + 语境判断）：
  - `grok`：英文舆论 / 实时讨论 / Twitter/X 语境 / 热点追踪（需 `GROK_API_KEY`）
  - `doubao`：火山方舟（托管 Doubao / DeepSeek / Kimi 等），中文语境 / 字节生态 / 中文热点（需 `DOUBAO_API_KEY`）
  - `gemini`：全球网页 / 英文综述 / 通用信息检索（需 `GEMINI_API_KEY`）
  - model 与后端特定选项由 `~/.config/search-crew/routing.yaml` 的 `ai_summary.models.<backend>.{fast,deep}` 决定，不在 env 配
- **全部 key 缺失**：自动回落到 `ai_summary.fallback_on_no_key`（默认 `jina`），与现有 `WEBSEARCH_FALLBACK` 机制一致
- **关闭整层**：用户态 `routing.yaml` 改 `ai_summary.enabled: false`
- **与硬规则的关系**：硬规则永远优先；AI 综述层只在「query 未命中任一硬规则」时启用

调用方式：

```bash
python3 search.py --query "..." --prefer ai                  # 让 search.py 自己按 selection_order 选
python3 search.py --query "..." --prefer ai --ai-backend grok # 显式指定哪一家
```

## 路由起点表

### 临床研究【硬规则】

- **必须**：site-search → `clinicaltrials.gov`（注册试验）
- **必须**：site-search → `pubmed.ncbi.nlm.nih.gov`（已发表文献）
- **禁止**：用通用搜索处理临床数据（数据权威性和时效性要求极高）

### 专利【硬规则】

- 国际：site-search → `patents.google.com` / `espacenet.com`
- 中国：site-search → `pss-system.cnipa.gov.cn`（国家知识产权局）/ `zhihuiya.com`（智慧芽）
- **禁止**：用通用搜索结果作为专利状态依据

### 学术论文

- **首选**：site-search → `arxiv.org`（开放论文）
- **配合**：site-search → `semantic-scholar.org`（带 metadata 和引用关系）
- **补充**：evidence-search 用 jina-search（找综述博客、对比文章）
- **不要**：用通用搜索找原始论文（结果质量差）

### 编程语言 / 框架 / 库的使用说明

- **首选**：site-search → context7（通用 LLM 文档 API）+ 该项目自家官方文档站
- 例：React → `react.dev`；Vue → `vuejs.org`；PyTorch → `pytorch.org`；Tailwind → `tailwindcss.com`
- **配合**：evidence-search 用 jina-search（找教程 / 博客 / Stack Overflow）

### 官方产品文档（云 / 工具 / 中间件）【硬规则】

- **必须**：site-search 到对应官方文档站
- 常见站点：`docs.aws.amazon.com` / `cloud.google.com` / `docs.docker.com` / `kubernetes.io` / `postgresql.org` / `redis.io` 等
- **禁止**：用通用搜索代替官方文档（版本错乱、过时严重）

### 代码与开源项目

- **首选**：site-search → github.com（精确代码 / repo / issue 搜索）
- **配合**：evidence-search 用 jina-search（找博客介绍、教程、对比）

### 包仓库

- **Python**：site-search → `pypi.org`
- **JavaScript**：site-search → `npmjs.com`
- **Rust**：site-search → `crates.io`
- **Go**：evidence-search 用 jina（Go 没有统一仓库 API）

### 通用技术调研

- **首选**：evidence-search 用 jina-search（语义搜索强）
- **配合**：evidence-search 用 serper（Google 精确关键词）
- **策略**：同一查询同时派两路，结果交叉验证

### 中文社区内容

- **首选**：evidence-search 用 serper 加 `language=zh-cn`
- **配合**：evidence-search 用 `site:zhihu.com` 间接抓知乎
- **注意**：知乎无公开 API，只能间接抓

---

## 站点适配器清单（程序化版本）

`python3 site_search.py --list-adapters` 列实时清单。基线包括：

| 站点 | 适配器 | 状态 |
|---|---|---|
| github.com | `lib/sites/github.py` | ✅ 需 GITHUB_TOKEN（可选） |
| developer.mozilla.org | `lib/sites/mdn.py` | ✅ |
| 任意 Algolia DocSearch 站 | `lib/sites/algolia.py` | ✅（已知索引：react.dev / tailwindcss.com / typescriptlang.org / vuejs.org / vitejs.dev） |
| pypi.org | `lib/sites/pypi.py` | ⚠️ best-effort（PyPI 无官方搜索 API） |
| npmjs.com | `lib/sites/npm.py` | ✅ |
| readthedocs.io | `lib/sites/readthedocs.py` | ✅ |
| 其他官方站 | 无 → 用浏览器 MCP / 用户态适配器 | 降级 |

## 何时降级到浏览器 MCP

满足任一条件时 site-search 才动用 Chrome DevTools MCP：

1. 站点是 SPA，搜索结果靠 JS 异步加载
2. 站点需要登录态才能搜索
3. URL 不可直接 deep link 到搜索结果
4. 上述 API 适配器全部失败

否则**必须**优先 API。

## 用户态扩展

用户可在 `~/.config/search-crew/adapters/` 加：

- `*.py`：代码型适配器（导出 `SITE` + `search` 函数）
- `*.yaml`：配置型适配器（URL 模式 + CSS selector）

加载顺序：用户 YAML > 用户 Python > Algolia 兜底 > 内置 Python。

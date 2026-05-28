# 扩展 Search Crew

## 三种常见扩展

### 0. AI 综述 backend（grok / gemini / doubao）

`borrow-smart-search-web-reader` change 引入。backend 用品牌命名；API key 走 env（secret），
model 走 routing.yaml（按 fast/deep 分层，不在代码 hardcode）。

| backend | 偏好场景 | API | env API key | model 配在哪 |
|---|---|---|---|---|
| `grok` | 英文舆论 / 实时讨论 / X | xAI Agent Tools API（`/v1/responses` + web_search） | `GROK_API_KEY` | `ai_summary.models.grok.{fast,deep}` |
| `doubao` | 中文语境 / 字节生态 / 中文热点（火山方舟，托管 Doubao / DeepSeek / Kimi 等） | 火山方舟 Responses API（`/api/v3/responses` + web_search） | `DOUBAO_API_KEY` | `ai_summary.models.doubao.{fast,deep}` |
| `gemini` | 全球综述 / 英文资料 / 通用检索 | Gemini `generateContent` + google_search grounding | `GEMINI_API_KEY` | `ai_summary.models.gemini.{fast,deep}` |

> **doubao（火山方舟）的坑**：routing.yaml 里的 model 必须是 API model ID（带日期的小写格式，如 `doubao-seed-2-0-pro-260215` 或 `deepseek-v4-flash-260425`），不是 console 显示名（如「Doubao-Seed-2.0-pro」）。模型要先在方舟控制台「开通管理」开通。列已开通 model：`curl -s https://ark.cn-beijing.volces.com/api/v3/models -H "Authorization: Bearer $DOUBAO_API_KEY"`。
>
> **grok 的坑**：旧 Live Search（`search_parameters`）已于 2026-01-12 废弃（HTTP 410），现走 Agent Tools API（`/v1/responses`）。三家都走各自的 Responses/Grounding API，不是普通 chat completions。

**model 分层**：`ai_summary.models.<backend>` 下分 `fast` / `deep` 两档。fast-search subagent 自动用 fast 档（便宜、量大），deep-search 用 deep 档（强、保质量）。tier 按派活的 subagent 名推断（名字含 `fast` → fast，其余 → deep），也可用 `search.py --tier fast|deep` / `--model <id>` 覆盖。

> **为什么 model 进配置而不写在代码里**：各厂商 model 版本号更新很快（带日期后缀），写死在代码里每次都要改源码。放 `routing.yaml` 后，换 model 只改一行配置、不动代码；fast/deep 分层也只是配置表的两行。

`defaults/routing.yaml` 当前各档默认值（可按需改）：

| backend | fast 档（省钱 / 量大） | deep 档（保质量） |
|---|---|---|
| grok | `grok-4-fast` | `grok-4.3` |
| doubao | `doubao-seed-2-0-mini-260428` | `doubao-seed-2-0-pro-260215` |
| gemini | `gemini-2.5-flash-lite` | `gemini-3.5-flash` |

**选型原则**：fast 档挑各家最轻量的（够拆查询词 + 消化网页即可），deep 档挑能力强的（要多轮判断、循证综合）。**不要**用 embedding / 纯基础档跑搜索——拆词和消化网页需要 tool calling + 一定推理力。

豆包（火山方舟）三档参考（≤32K 输入，元 / 百万 token，2026-02 官方分段计费）：

| 档 | model id | 输入 | 输出 | 第三方实测准确率 | 定位 |
|---|---|---|---|---|---|
| mini | `doubao-seed-2-0-mini-260428` | 0.2 | 2 | 71.8% | 最轻量、低时延高并发——**默认 fast 档** |
| lite | `doubao-seed-2-0-lite-260428` | 0.6 | 3.6 | 73.9% | 均衡，性价比高 |
| pro | `doubao-seed-2-0-pro-260215` | 3.2 | 16 | 76.5% | 旗舰，复杂推理——**默认 deep 档** |

调用：

```bash
python3 search.py --query "..." --prefer ai                  # 按 routing.yaml selection_order 选
python3 search.py --query "..." --prefer ai --ai-backend grok # 显式指定 backend
python3 search.py --query "..." --prefer ai --tier deep       # 显式指定档位
```

**关闭整层**：`~/.config/search-crew/routing.yaml` 改 `ai_summary.enabled: false`，回到原有 jina / serper 路径。

**加第四家**（如 Anthropic / OpenAI 加入综述能力）：

1. `skills/search-toolkit/scripts/lib/backends/ai_<name>.py`：仿 `ai_grok.py` 写 `BACKEND` / `is_available()` / `search(query, *, max_results, model)`，调 `make_envelope` 装统一结构
2. `lib/backends/__init__.py` 把新模块加进 `__all__`
3. `scripts/search.py` 的 `AI_BACKEND_MODULES` dict 注册 + `_AI_BACKENDS`（`lib/_http.py`）加名字
4. `defaults/routing.yaml` 把新名字加入 `ai_summary.selection_order` 并在 `ai_summary.models` 下加 fast/deep
5. `defaults/pricing.yaml` 加 backend 段（暂可填 null 等后续补单价）
6. `.env.example` 加新 API key 环境变量

### 1. 新增通用搜索 backend（如 Brave Search / Tavily）

适合：你想接入一个新的"通用搜索引擎"类型 API。

步骤：

1. 在 `skills/search-toolkit/scripts/lib/` 加新模块（如 `brave.py`），仿照 `jina.py` / `serper.py` 写：
   - `is_available()` 检查环境变量
   - `search(query, *, max_results, language) -> list[normalize_result]`
   - 所有 HTTP 请求经 `lib/_http.py` 的 `request_json` / `request_text`（含 `backend=`、`endpoint=` 用于打点）
2. 改 `scripts/search.py` 把新 backend 加入路由（`--prefer` 选项 + 默认顺序）
3. 在 `defaults/pricing.yaml` 加单价表
4. （可选）在 `.env.example` / README 文档化新环境变量

### 2. 新增站点适配器（用户态，不动 plugin）

**推荐方式**——零侵入，跟随 plugin 升级不丢失。

#### 方式 A：YAML 配置型（零代码）

适合：站点搜索是简单的 `GET https://site.com/search?q=...` + 静态 HTML 列表。

在 `~/.config/search-crew/adapters/<site>.yaml`：

```yaml
site: example.com
search_url: "https://example.com/search?q={query}"
result_selector:
  list: ".result-item"        # 每条结果的 CSS class
  title: "h3 a"               # 在每条 list 内查标题
  url: "h3 a@href"            # @href 取属性
  snippet: ".excerpt"
```

selector 子集见 `lib/sites/_yaml_adapter.py` 注释。复杂站点用方式 B。

#### 方式 B：代码型（Python）

适合：需要认证 / 分页 / JSON API / 复杂解析。

在 `~/.config/search-crew/adapters/<name>.py`：

```python
"""复制 / 改写自 https://github.com/<某人的现成实现>，遵守原仓库 LICENSE。"""

from typing import Any

SITE = "example.com"


def search(query: str, max_results: int = 10, **_: Any) -> list[dict[str, Any]]:
    # ... 你的实现
    return [
        {"title": "...", "url": "...", "snippet": "...", "extra": {...}},
        ...
    ]
```

**强建议**（USER_DESIGN P-AGENT-003）：动手写前**先**去 GitHub / 搜索引擎查现成实现，参照而不是闭门造车。

### 3. 新增站点适配器（plugin 内置）

需要：你的适配器对所有 Search Crew 用户都有价值，想随 plugin 分发。

步骤：

1. 在 `skills/search-toolkit/scripts/lib/sites/` 加模块（`SITE = "<host>"` + `search(...)`）
2. 在 `lib/sites/__init__.py` 的 `BUILTIN_REGISTRY` 注册
3. 写测试 → PR

如果是 Algolia DocSearch 站点：

1. 在浏览器开发者工具抓站点的 `app_id` / `api_key` / `index_name`
2. 加进 `lib/sites/__init__.py` 的 `ALGOLIA_INDEXES`
3. 不需要写代码

## 增强 web-page-fetch（读取网页 / 文件）

`web-page-fetch` skill 让主 agent 读 URL 时优先用 `fetch.py`（对标内置 WebFetch），是一个**会持续增强**的底座。当前实现：

- **HTML**：直连探测 Content-Type 为 `text/html` → 送 Jina Reader 渲染（处理 JS、干净 markdown）
- **raw**：`text/plain` / `text/markdown` / `application/json` / 源码等 / 无 HTML 标签 → 原文直取，不经 Jina
- **反爬识别**：短内容 + 命中 `环境异常` / `去验证` / `captcha` / `滑块` 等签名 → 判 `anti_bot`，不当正文
- **读取豁免站点调用上限**（上限只管搜索源）

判定逻辑在 `skills/search-toolkit/scripts/fetch.py`：`_is_raw_content_type`（Content-Type + HTML 标签兜底）、`_looks_blocked`（反爬签名）。要加新源类型 / 解析器在此扩展。

**已知不支持**：微信公众号（`mp.weixin.qq.com`，风控 + 滑块，合规手段过不去）。

**未来方向（[backlog B-006](./openspec/project.md)）**：接入 [OpenCLI](https://github.com/jackwener/OpenCLI) 的 `opencli-browser` 作进阶后端（处理 JS 重 / 非验证码登录墙），agent 内部用、不暴露给用户；需先有远程化调用版本（不依赖本地常驻 Chrome）。

## 未来候选 backend / 适配器（B-005 之后）

不在当前 change 范围内，欢迎以后单起 change 加入：

- arxiv（学术）
- semantic-scholar
- google-patents
- clinicaltrials.gov
- pubmed
- HackerNews（Algolia）
- 知乎（间接，需走浏览器 MCP）

## 修改路由起点

直接改 `~/.config/search-crew/routing.yaml`：

- 加 / 删主题
- 把 hard_rule: true 关掉（变成强建议）
- 调主题对应的起点站

升级 plugin 不影响。

## 修改 cost 单价

直接改 `~/.config/search-crew/pricing.yaml`。`last_updated` 字段记得顺手改。

## 自定义 subagent 上限

`~/.config/search-crew/limits.yaml`：

- `deep_search.max_rounds`：deep-search 最多跑几轮
- `deep_search.per_round_breadth`：每轮并行派几个
- `fast_search.max_results`：每次抓多少结果
- 等

## 写新 OpenSpec change

任何会改变对外行为的扩展（新 P-* 行为、改变 USER_DESIGN）都建议走 OpenSpec：

1. `openspec/changes/<change-id>/proposal.md`：动机、范围、非目标
2. `openspec/changes/<change-id>/USER_DESIGN.md`：新 P-* 行为台账（**需用户确认**）
3. `openspec/changes/<change-id>/TECH.md`：技术决策 T-*
4. `openspec/changes/<change-id>/design.md`：临时设计推演
5. `openspec/changes/<change-id>/tasks.md`：执行 + 验证清单
6. `openspec/changes/<change-id>/capabilities/<name>/spec.md`：能力 spec

参考已有的 `init-search-crew` / `add-usage-tracking` 两个 change 的目录结构。

## 配置写入与 `$CLAUDE_PLUGIN_ROOT` 的坑

`~/.config/search-crew/` 的写入只走三个固定脚本操作（见 charter `I-LEARN-001`）：

- `seed_user_config.py`（首次拷 defaults）
- `seed_user_config.py --merge`（补缺失顶层段；`--dry-run` 只检测不写）
- `promote.py <pending-file>`（pending → active 晋升）

三者都会向 `~/.config/search-crew/changelog.log` 追加一条记录。**AI / LLM 禁止用编辑器手改 active 任何文件**——要补配置就跑这些脚本，不要 Edit。

**坑**：`$CLAUDE_PLUGIN_ROOT` 只在 plugin 自己的 command / agent 执行时被注入；在用户的交互 `!` shell 里它**是空的**，`python3 $CLAUDE_PLUGIN_ROOT/.../seed_user_config.py` 会解析成 `/.../` 直接报「文件不存在」。所以：

- **别把依赖 `$CLAUDE_PLUGIN_ROOT` 的命令丢给用户手敲**；该由主 agent（command 上下文里有该变量）自己跑，或写绝对路径。
- 上述脚本本身用 `__file__` 自解析 plugin 路径，**不依赖**该变量——直接给脚本绝对路径就能跑。

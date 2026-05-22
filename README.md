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
/plugin marketplace add mycrew-labs/search-crew    # 从 GitHub
# 或：/plugin marketplace add ~/path/to/search-crew  # 从本地 checkout
/plugin install search-crew@search-crew
/setup                                             # 检查 backend / Chrome / 引导
```

可选 API key（不配置也能用）：复制 `.env.example` 到 `~/.zshrc` 填入。

## 本仓库开发者：激活 git hook

clone 本仓库后跑一次（激活 OpenSpec 归档检查 pre-commit hook）：

```bash
git config core.hooksPath .githooks
```

hook 脚本在 `.githooks/pre-commit`（随仓库走，更新会随 `git pull` 到位）。激活后每次 commit 自动检查「有 change 实施完成但未归档」的情况。

## 三层入口

| 场景 | 触发方式 |
|---|---|
| 日常关键词搜索 | 对话直接说「查一下...」/「找几个...」自动派 fast-search |
| 站内精确搜索 | 对话直接说「去 X 官网查...」自动派 site-search |
| 深度循环调研 | `/deep-search <主题>` 手动触发 |
| 查历史使用 | `! python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/usage.py --last 10` |

## 扩展

见 [EXTENDING.md](./EXTENDING.md)：

- 新增通用搜索 backend（Brave / Tavily 等）
- 新增站点适配器（YAML 配置型 / Python 代码型，用户态零侵入）
- 修改路由起点 / cost 单价 / subagent 上限

## 状态

- ✅ 第一阶段（init-search-crew）：三个 subagent + skills + commands + defaults 全部就位
- 🚧 持续接入：B-001 ~ B-005 见 [project.md](./openspec/project.md)

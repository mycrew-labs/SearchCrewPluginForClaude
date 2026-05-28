# USER_DESIGN

> 本文件是项目的 **charter 层**：vision、不可违反的项目级不变量、所有权约束。
> 所有可写成 BDD scenario 的具体行为放在 `openspec/specs/<capability>/spec.md`，**不**写在本文件。
>
> 本文件由**用户**拍板；AI 不得自行新增 / 修改 / 删除任何条目。

## Vision

这虽然是一个搜索工具，但**如何让用户理解数据的关联关系**、**如何真正把循证传递下去**，才是它优化的方向。

三条长期主轴：

1. **数据关联关系** —— 产物目录组织、ranking、关键词索引、wiki 风格大纲、附件去重，让主模型和用户能像浏览一个陌生但结构清晰的代码库一样自助导航。
2. **循证传递** —— 搜索过程严格循证（先官方源 → 扩展 → 关键结论回官方源复核），结论使用阶段强制保留原始证据（URL、原文摘录、关键数字）。
3. **自我进化**（长期） —— 把 [karpathy/autoresearch](https://github.com/karpathy/autoresearch) 的 checklist 评分 + 山爬迭代引入站点适配器与查询策略的自动优化。

## 项目级不变量（不可违反）

| 编号 | 不变量 |
|---|---|
| **I-CONFIG-001** | `~/.config/search-crew/` 是 runtime **唯一**配置真相；首次安装从 plugin `defaults/` 一次性拷贝；之后 plugin 升级**不动** active；用户对 active 拥有完全所有权 |
| **I-DATA-001** | run 产物落在 `/tmp/search-crew/<session_id>/`；plugin **不写入**用户项目目录，除非用户明确同意复制 |
| **I-EVIDENCE-001** | 主 agent / subagent 向用户呈现任何来自搜索的结论时，**必须**附带循证证据：URL 必填，关键原文 / 数字按需 |
| **I-PARALLEL-001** | 同 turn 内派发多个 subagent 必须一次性发起；派发前必须先调 `TaskCreate` |
| **I-CONTEXT-001** | 给用户展示的 cost 总览**只一行**进 context；明细 / 历史走落盘文件或 `!` shell 命令，不污染主 agent context |
| **I-LEARN-001** | AI **MUST NOT** 用编辑器手改 active 配置任何文件。AI 自发的建议（学到的路由 / 适配器）必须写 `pending/` 由用户审核晋升；用户**显式授权**下的维护（补 defaults 段、晋升 pending）只能经约定好的固定脚本操作（`seed` / `merge` / `promote`）完成，每次写入追加 changelog |
| **I-BRAND-001** | 品牌归属 MyCrew；GitHub org `mycrew-labs`；Docker Hub namespace `mycrew` |
| **I-FALLBACK-001** | plugin 在零 API key 状态下必须仍能完成基本调研（fallback 到 Claude Code 内置 WebSearch / WebFetch） |

## 所有权与变更门禁

- **本文件（`USER_DESIGN.md`）**：用户拥有。AI 修改前必须单独提请确认。
- **`openspec/TECH.md`**：AI 拥有，可按需迭代。重大架构转向 SHOULD 主动告知用户。
- **`openspec/specs/<capability>/spec.md`**：AI 拥有，按 OpenSpec CLI workflow（`openspec new change` → 实施 → `openspec archive`）管理。
- **`openspec/changes/<id>/`**：进行中的变更。每个 change 内允许有 USER_DESIGN delta，AI MUST 先经用户确认才能合入。

## 阶段路线图

- **第一阶段（已落地）**：三个 subagent、循证工作流、产物组织、配置生命周期、Stop hook 学习闭环、API cost 统计
- **第二阶段（Backlog B-001 ~ B-005）**：自建 markitdown 类镜像、microsandbox 集成、autoresearch 式适配器自动优化

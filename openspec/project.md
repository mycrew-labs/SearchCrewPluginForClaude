# Search Crew Plugin

Claude Code plugin，为调研类任务提供三层能力：快速搜索、站点精确搜索、深度循环挖掘。通过文件系统作为中介实现 context 隔离。

## 品牌归属

- 项目品牌：**MyCrew**（Search Crew 是 MyCrew 旗下首个 plugin）
- GitHub org：<https://github.com/mycrew-labs>
- Docker Hub namespace：<https://hub.docker.com/repositories/mycrew>

## OpenSpec 治理

本项目采用 [OpenSpec CLI](https://github.com/Fission-AI/OpenSpec)（`openspec` 命令）治理规格与变更：

- `openspec/project.md`（本文件）：项目概览 + Backlog
- `openspec/USER_DESIGN.md`：项目级**charter**（vision、不可违反的不变量、所有权约束），用户拥有
- `openspec/TECH.md`：项目级**ADR**（架构决策），AI 拥有可迭代
- `openspec/specs/<capability>/spec.md`：单能力 BDD spec（`### Requirement:` + `#### Scenario:`），`**Lock**: user-confirmed` 标记的需求改动门禁与 USER_DESIGN 同级
- `openspec/changes/<id>/`：进行中的变更（通过 `openspec new change <name>` 创建，`openspec archive <name>` 归档）

详细分层与门禁规则见 `$AI_HOME/rules/change-flow.md`。

## 历史说明

本项目首版 spec 体系是手写的 P-/T- 编号台账（USER_DESIGN/TECH 各 19 条 / 22 条），跟 OpenSpec CLI 期望的 BDD 格式不兼容。2026-05-21 完成一次性重构：

- USER_DESIGN.md 收缩为 8 条 I-* 不变量 + Vision + 所有权（charter 形态）
- TECH.md 收缩为 9 条 T-* 架构决策（ADR 形态）
- 19 条 P-* 详细行为重写为 6 个 capability spec 下的 BDD requirement，全部标 `**Lock**: user-confirmed` `**Confirmed-At**: 2026-05-21`
- 未来所有新功能走 OpenSpec CLI 标准 workflow（`openspec new change` → propose → specs → tasks → archive）

git 历史保留了首版手写 spec 全貌（commit `37be618` 与 `3b743cc`），便于追溯设计演化。

## Backlog（项目级长期待办）

> 当前不在任何进行中 change 的范围内；后续按需起新 change（`openspec new change <name>`）。

- **B-001 自建文档转 Markdown 镜像**：参考 / 借鉴 [docling](https://github.com/docling-project/docling) 与 [markitdown](https://github.com/microsoft/markitdown)，将文档（PDF / DOCX / PPTX / XLSX / HTML / 图片 / 音频 / EPub / ZIP 等）转 Markdown 的能力编译成 Docker 镜像，发布到 `hub.docker.com/repositories/mycrew`。
- **B-002 轻量运行环境**：调用方式参考 [microsandbox](https://github.com/superradcompany/microsandbox)，让用户客户端只需安装一次轻量级运行环境，无须长驻 daemon，每次像执行命令一样完成转换。
- **B-003 集成进 Search Crew**：把 B-001 / B-002 的能力作为 fetch / site-search 的转换后端之一，让抓回来的非文本资源也能进入 Markdown 流。
- **B-004 autoresearch 式适配器自动优化**：把 [karpathy/autoresearch](https://github.com/karpathy/autoresearch) 的「checklist 评分 + 山爬迭代」流程引入「新增 / 优化站点适配器与查询策略」的过程。
    - **评判函数**：本场景特别清晰——能不能找到内容、多次运行的稳定性、速度、准确性，都是天然可量化的维度。
    - **优化循环**：参考 autoresearch 的 5 步法（小改 prompt / 适配器代码 → 跑 10 个测试用例 → 用 3-6 个是/否 checklist 打分 → 比上一轮高就保留，低就回滚 → 重复直到连续 3 轮 >90% 或人喊停）。
    - **落地形态**：新建适配器 / 调整查询条件时，可以让一个独立 agent 按这套流程自动迭代；产物是一份打分日志 + 最终采纳的版本，走 Pending → Active 通道供用户审核。
- **B-005-ext usage-tracking 扩展**：B-005 首版（usage-summary + 永久持久化 + usage.py CLI）已落地；扩展方向：
    - 月度 / 日度报告 + 阈值告警
    - Stop hook 提示带本次 cost summary
    - cost 写进 deep-search `report.html`
- **B-006 web-page-fetch 接入「远程 browser-host API」处理需登录/付费内容（agent 内部用，不暴露给用户）**：让 `web-page-fetch` 在 `blocked: needs_auth`（登录墙 / 付费墙，如付费 paper PDF）时，调一个远程 API 用**真实登录态浏览器**把内容拿回来。**对验证码墙（如微信）无效**——那只能 honest / 用户贴。
    - **核验事实（2026-05-26 读 OpenCLI README）**：[OpenCLI](https://github.com/jackwener/OpenCLI) 强依赖本地 Chrome + Browser Bridge 扩展 + 本地 daemon + 登录态会话，**无远程/headless 模式**；以 skill 分发（`opencli-browser`，也是用户 web-reader/smart-search 的底座）。它的真正定位是「用你登录态会话拿要登录的内容」，不是通用公开页抓取。
    - **架构（A/B 拆分）**：
        - **A. browser-host API 服务（独立项目/repo）**：在一台有 Chrome+扩展+登录态的机器上跑 OpenCLI，外加一层 HTTP 包装把「只读抓取指定 URL」暴露成 API。OpenCLI 原生不给 HTTP，这层要自己写。
        - **B. search-crew 客户端集成（本项）**：一个 fetch backend，在 needs_auth 时调 A 的远程 API 拿 markdown。search-crew 只是薄客户端，重活在 A。
    - **远程化目的**：避免每台开发机都要 GUI + 开 Chrome + 装高权限插件；无头开发机远程调一台 browser-host。
    - **安全（命门，缺一不可）**：该 API 背后是你登录态真实 Chrome（能读你邮箱/银行/付费账号），暴露公网风险极高。
        1. 优先**私有 overlay**（Tailscale / WireGuard / Cloudflare Tunnel+Access），**别裸 frp 暴露公网**；要 frp 也必须叠 TLS + 强鉴权
        2. 强鉴权：mTLS 客户端证书或长随机 token + IP 白名单（非 basic auth）
        3. 最小权限：host 用**专用 Chrome profile**，只登必要账号
        4. 能力收窄：API 只暴露「只读抓取指定 URL」，**不**开放点击/填表/执行 JS 等全套 browser 原语
        5. 审计：每次远程调用落日志
    - **降级**：远程 host 不可达（Chrome 没开/网络断）→ 优雅落回 `on_blocked` 策略（honest / collaborate），不中断主流程。
    - 属 `web-page-fetch`（`public-fetch-and-command-rename` change 引入）的后续增强；客户端插入点已在该 change 预留。

## 关联规则

- 全局：`$AI_HOME/AGENTS.md`、`$AI_HOME/rules/change-flow.md`
- Python 脚本编码规范：`$AI_HOME/rules/coding/python.md`
- 临时脚本依赖：PEP 723 + `uv run`（见 `rules/change-flow.md` 临时脚本节）

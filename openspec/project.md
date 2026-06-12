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
- **B-006 web-page-fetch 接入「远程 browser-host API」处理需登录/付费内容 —— ✅ 已落地，实现方案由 OpenCLI 改为 [universal-page-fetcher](https://github.com/mycrew-labs/universal-page-fetcher)（2026-06-12，change `upf-fetch-backend`）**：最终形态是「真实已登录浏览器 + Cloudflare Worker 网关」的独立项目，本插件客户端在 `lib/real_browser.py`（Bearer 鉴权 + 轮询 + coverage 残缺判失败），经 `fetch.py --real-browser` 分派（域名直达 + 被挡升级）。它还攻克了本条目当年判定无解的微信公众号与虚拟滚动长文档（飞书 / Notion / 语雀）。以下 OpenCLI 方案调研笔记**保留作历史记录**（其安全分析对任何「暴露登录态浏览器」的方案仍有参考价值），方案本身不再实施：
    - 原设想：让 `web-page-fetch` 在 `blocked: needs_auth`（登录墙 / 付费墙，如付费 paper PDF）时，调一个远程 API 用**真实登录态浏览器**把内容拿回来。当时判定「对验证码墙（如微信）无效」——后被 universal-page-fetcher 的真实浏览器 + 设备原生指纹方案推翻。
    - **核验事实（2026-05-26 读 OpenCLI 源码/文档）**：[OpenCLI](https://github.com/jackwener/OpenCLI) 的 CLI ↔ daemon ↔ 扩展通信 = **WebSocket `127.0.0.1:19825`**（daemon 是 WS server，CLI 和 host Chrome 扩展都连它）——**是端口，不是 native messaging**，故可跨 Docker 边界。OpenCLI 文档（`docs/guide/remote-orchestration.md`）明确**警告别暴露 daemon 端口**：协议无鉴权，谁连上谁就能读所有登录态 cookie / 在任意标签执行 JS（「扩展连远程 daemon」#636 已搁置，待 daemon 加鉴权）。
    - **运行环境约束（2026-05-27 确定）**：**只支持带桌面的 Linux**（Mac 因 Docker Desktop VM 不共享宿主 loopback，`network_mode: host` 行不通——暂不管）。host 只需：Chrome（装 OpenCLI 扩展，理想用 `--load-extension` 自动加载）+ Docker + 桌面 GUI。
    - **架构（2026-05-27 定稿）**：
        - **A. browser-host 镜像（独立项目/repo）**：**把 OpenCLI 全套（node + opencli CLI + daemon）连同一层 HTTP 包装服务打进同一个 Docker image**。容器用 `network_mode: host`，容器内 daemon 绑 `127.0.0.1:19825` = 宿主 loopback，host Chrome 扩展直接连得到。API 服务收 HTTP 请求 → 容器内 shell `opencli browser ...` → 返回抓取内容。
        - **B. search-crew 客户端（本项）**：web-page-fetch 在 `needs_auth` 时**只拼一个简单 HTTP 请求**（如 `GET /fetch?url=...`）调 A 的接口拿 markdown。**客户端零 opencli 依赖**（不再要求本地装 opencli 包）——这是把 opencli 全塞进镜像的核心目的。
    - **安全（命门）**：raw daemon 无鉴权（OpenCLI 自己警告），所以**暴露的是 A 的 HTTP 包装服务、不是 daemon**；包装层负责：① 强鉴权（长随机 token / mTLS，非 basic auth）；② **能力收窄**：只暴露「只读抓取指定 URL」，不开放点击/填表/执行 JS 全套 browser 原语；③ 私有 overlay（Tailscale / WireGuard / Cloudflare Tunnel）优先，别裸 frp 暴露公网，要 frp 必叠 TLS + token + IP 白名单；④ host 用**专用 Chrome profile** 只登必要账号；⑤ 每次调用落审计日志。
    - **降级**：A 不可达（Chrome 没开 / 网络断 / 容器挂）→ 优雅落回 `on_blocked` 策略（honest / collaborate），不中断主流程。
    - 属 `web-page-fetch`（`public-fetch-and-command-rename` change 引入）的后续增强；客户端插入点已在该 change 预留。

## 关联规则

- 全局：`$AI_HOME/AGENTS.md`、`$AI_HOME/rules/change-flow.md`
- Python 脚本编码规范：`$AI_HOME/rules/coding/python.md`
- 临时脚本依赖：PEP 723 + `uv run`（见 `rules/change-flow.md` 临时脚本节）

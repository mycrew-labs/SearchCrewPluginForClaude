# Tasks: upf-fetch-backend

## 1. 门禁与配置

- [x] 1.1 locked 需求变更确认：向用户单独提请「web-page-fetch 按 on_blocked 策略分派 + 已知不支持站点」（Lock: user-confirmed, 2026-05-26）的删除与替换，确认后方可动实现代码
- [x] 1.2 `defaults/limits.yaml`：删除 `web_page_fetch.remote_host` 段，新增 `web_page_fetch.real_browser`（`direct_domains` 默认清单 + `wait_sec: 480`），注释说明连接配置归 universal-page-fetcher 自有约定、本文件只管分派策略

## 2. fetch.py 实现

- [x] 2.1 `lib/_http`：若现有 helper 不暴露 status code，新增返回 `(status, body)` 的薄函数（保持打点与 cap_exempt 语义）
- [x] 2.2 新增升级层模块逻辑：连接配置读取（env → `~/.config/universal-page-fetcher/config.json`，缺失即不可用）、每进程一次 `/health` 探测缓存、轮询状态机（202 + jobId 续等、2s 间隔、网络抖动容错连续 10 次、`wait_sec` 总预算、401/503 不重试）、密码不入任何输出
- [x] 2.3 删除 `_try_remote_host()` 及 OpenCLI 相关 docstring；接入新分派：`--real-browser` 开关（默认关）、域名直达（命中 `direct_domains` 跳过普通链，失败回落 + `warning` 字段）、被挡升级（anti_bot / needs_auth 先试升级层）、`coverage.suspectIncomplete` 判失败
- [x] 2.4 成功输出形态：`source: "universal-page-fetcher"`，透传 `title` / `coverage`

## 3. 测试

- [x] 3.1 `tests/test_fetch.py` 扩展（mock HTTP）：默认关不发升级请求；开关开 + 被挡 → 先升级；域名直达命中/未命中；直达失败回落带 warning；suspectIncomplete 判失败；未配置静默跳过；401 输出不含密码值
- [x] 3.2 全量跑 `tests/` 确认无回归

## 4. 文档同步

- [x] 4.1 `skills/web-page-fetch/SKILL.md`：示例命令改 `--real-browser` 并指引 Bash timeout 600000ms；删除「微信公众号已知不支持」段；新增升级路径、warning 字段处理、未配置时的表现；删除 B-006 表述
- [x] 4.2 调研路径检查：grep 确认 evidence-search / site-search 等 agent 与 skill 文档中的 fetch.py 用法均不带 `--real-browser`，必要处加一句「MUST NOT 带升级开关」
- [x] 4.3 `openspec/project.md`：B-006 改记「已被 universal-page-fetcher 取代（2026-06-12）」，OpenCLI 调研笔记保留为历史；README 等若有「微信不支持」表述一并同步
- [x] 4.5 OpenCLI 痕迹全量扫净（2026-06-12 盘点，grep -i opencli 共 10 文件）：`defaults/pricing.yaml`（opencli-remote 计费条目）、`skills/search-toolkit/SKILL.md`（抓取链描述）、`commands/search-skill-setup.md`（remote_host 配置指引段）、`EXTENDING.md`（未来方向段）一并替换为 universal-page-fetcher 表述；`README.md` 版本历史 0.7.1 句保留不动（历史记录，循 0.8.2 先例）；完成后 `grep -rni opencli` 仅剩 README 历史与 openspec 归档/本 change 文档
- [x] 4.4 universal-page-fetcher 仓库（另一 checkout，单独 commit）：调用方 skill / README 加一句「与 SearchCrew 同用时，入口统一走 web-page-fetch」

## 5. 收尾

- [x] 5.1 `openspec validate --all` 通过；完工简报（拟加锁清单 + 知识沉淀）提请用户确认后归档
- [x] 5.2 提醒用户自行处理本机 `~/.claude/skills/universal-page-fetcher/`（红线目录，AI 不代删）

## 6. 简报反馈调整（2026-06-12 用户拍板）

- [x] 6.1 需求②改「按需显式开启」：撤销调研 subagent 禁用，所有调用方自行判断必要性；同步 spec delta / design D1 / proposal / agent 文档 / 两处 SKILL.md / limits.yaml 注释 / fetch.py 文案
- [x] 6.2 需求③文档扩写：直达清单从列域名改为「按类别说明收录理由」（虚拟滚动正文残缺探测不到 / 微信风控墙）
- [x] 6.3 三条需求落锁 Lock: user-confirmed（2026-06-12）；版本 1.0.4 → 1.1.0（两处 json + README 历史）

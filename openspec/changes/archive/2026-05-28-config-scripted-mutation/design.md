## Context

active 配置 `~/.config/search-crew/` 的写入现状：

- `seed_user_config.py`（无参）：首次拷 defaults，幂等，有文件锁。
- `seed_user_config.py --merge`：把 defaults 里 active 缺的**顶层段**作为原始文本块追加到对应文件末尾（`_merge_yaml_file` 已返回追加的 key 列表，但只打 stderr，未落 log）。
- **晋升**：`stop_hook.py` 只输出提示，真正把 pending 规则并进 active 由 **AI 手改** `routing.yaml` 完成——无脚本、无 log，且违反 I-LEARN-001 的精神。

`routing.yaml` 结构：顶部注释 + `last_updated` + `topics:`（list，每项 `{name, description, sites, hard_rule}`）。`adapters/` 放 YAML / Python 适配器文件。pending 在 `pending/{routing,adapters}/<timestamp>-<slug>.yaml`。

YAML 写入用项目自带的极简文本切块（`_split_top_level_blocks`），**按文本块操作、不 round-trip 序列化**，以保住用户的注释和排版。

## Goals / Non-Goals

**Goals:**
- 把 active 的 AI 写入收敛成有限几个**固定脚本操作**：`seed` / `merge` / `promote`，是 AI 写 active 的唯一途径。
- 禁止 LLM 用编辑器手改 active 任何文件（精准性 + 防误伤无关内容）。
- 每次脚本写入 active 追加 `changelog.log`（seed / merge / promote 三类）。
- `merge` 加 `--dry-run`：只报缺哪些段、不写盘，供 setup 先问后做。
- setup 检测缺段 → 问用户 → 确认后 AI 自己跑 merge（脚本自解析路径，不依赖 `$CLAUDE_PLUGIN_ROOT`）。
- 重写 charter `I-LEARN-001` + config-lifecycle locked 需求为双通道模型。

**Non-Goals:**
- 不做"AI 按用户口述改任意配置值"的通用 set 操作（如无必要勿增实体；用户要改具体值仍自己编辑文件，那种手改本就无法也无需记 log）。
- 不改 pending 学习区的产生方式、Stop hook 的提示触发（只改晋升的*执行*环节）。
- 不引入 YAML 序列化库（保持零依赖 + 注释安全的文本块策略）。

## Decisions

### D1：active 的三个固定写入操作
| 操作 | 入口 | 行为 |
|---|---|---|
| `seed` | `seed_user_config.py` | 首次拷 defaults，幂等（不变） |
| `merge` | `seed_user_config.py --merge [--dry-run]` | 补缺失顶层段；dry-run 只报不写 |
| `promote` | `promote.py <pending-file>`（单独脚本） | pending 规则并进 active，成功后删 pending 文件 |

`promote` 单独成脚本（不并入 `seed_user_config.py`）：seed/merge 是"defaults → active"的安装期搬运，promote 是"pending → active"的运行期晋升，语义与触发时机不同；文本块工具与 changelog 辅助下沉到 `lib/`，两脚本各自 import 复用，不靠塞进同一 main 来共享。

### D2：promote 的合并机制（文本块，不序列化）
- **routing pending**：文件内容是一个 `topics:` 列表项（缩进好的 YAML 片段）。promote 定位 active `routing.yaml` 的 `topics:` 块，把该项**追加到块末尾**（保持缩进），其余一字不动。
- **adapters pending**：文件是完整适配器（YAML 或 .py）。promote 把它**移动**到 `adapters/<name>`，重名则报错让用户改名，不覆盖。
- promote 成功后**删除**对应 pending 文件（已消费），并写 changelog。
- 失败（格式不符 / 重名 / 定位不到 `topics:`）→ 非零退出 + 明确错误，不留半成品。

### D3：changelog 格式
`~/.config/search-crew/changelog.log`，每行一条，追加写（never rewrite）：
```
2026-05-28T14:03:11Z  merge   limits.yaml      +wide_search                      trigger=setup
2026-05-28T14:05:02Z  seed    (init)           routing,pricing,limits,adapters   trigger=first-install
2026-05-28T14:09:30Z  promote routing.yaml     +topic:rust-crates                trigger=user-approved
```
字段：UTC 时间戳 / 操作 / 目标文件 / 改了什么（紧凑摘要）/ 触发来源。由 `lib` 的一个 `append_changelog()` 辅助统一写，带文件锁。AI 永不手写该文件。

### D4：dry-run 与 setup 流程
- `--merge --dry-run`：跑 `_merge_yaml_file` 的"算缺失 key"部分但不写盘，stdout 输出机器可读结果（如每文件缺哪些段），供 setup 判断。
- `commands/search-skill-setup.md` 检查阶段：跑 `--merge --dry-run` → 有缺段 → `AskUserQuestion`「检测到 active 缺 X 段，补齐吗？」→ 用户确认 → AI 跑 `--merge`（脚本自解析路径）。**不再**给用户贴 `$CLAUDE_PLUGIN_ROOT/...` 命令。

### D5：I-LEARN-001 / config-lifecycle 重写措辞
双通道模型：
- AI 自发建议 → `pending/`，永不直接进 active（不变）。
- 用户**显式授权**下，AI 可写 active，但**仅经** `seed`/`merge`/`promote` 这组固定脚本操作，**禁止用编辑器手改** active 任何文件；每次写入追加 changelog。

## Risks / Trade-offs

- **promote 文本块合并的脆弱性**：`topics:` 块定位 + 缩进拼接靠极简解析，pending 片段格式不规范会出错。缓解：promote 校验片段能被 `_split_top_level_blocks` / 缩进规则识别，不符就报错不写；加测试覆盖 routing/adapters 两类 + 重名 + 坏格式。
- **改 locked charter 不变量**：`I-LEARN-001` 是用户所有的 charter，MODIFY 必须用户确认（归档前锁确认 gate）。
- **changelog 不全**：用户手改文件感知不到、不记——已与用户对齐，接受。changelog 只承诺"脚本写入"的完整性，不承诺"active 的全部变更"。
- **拆分脚本的共享成本**：promote 单独成脚本，文本块切块工具（`_split_top_level_blocks`）与 changelog 辅助 MUST 下沉到 `lib/` 供两边 import，否则会重复实现。本次顺带把 `_split_top_level_blocks` 从 `seed_user_config.py` 移到 `lib/`。

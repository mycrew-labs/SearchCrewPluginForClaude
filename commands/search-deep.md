---
name: search-deep
description: 启动一次深度调研。主 agent 派 deep-search subagent 规划 + 多轮派活 + 综合，最终产出 HTML + Markdown 双格式报告。
---

## 用户主题

`{{args}}`

## 主 agent 工作流（作为 Leader）

### 1. TaskCreate 建任务清单

派 deep-search 之前先调 `TaskCreate`，描述面向用户：「深度调研 ：{{args}}」。

### 2. 协作邀请（P-UX-001）

向用户输出一行简洁、非阻塞的提示（注意是真实显示给用户，不是内心独白）：

> 💡 如果你已经知道权威数据源或希望使用的查询条件，可以直接贴进来，AI 会优先采用。

### 3. 派 deep-search subagent

用 Task 工具派 `deep-search`，参数：

- `topic`：原样传 `{{args}}`
- `purpose`：如果你能从用户措辞推断更具体的意图，加这一段
- `target_dir` 不传，让 deep-search 自己用 session-id 决定

### 4. 等返回

deep-search 会返回三行：

```
<run_root>/deep-search/report.html
<run_root>/deep-search/report.md
本次估算 ~$X.XXX USD（N 次调用 · ...）
```

记下 `<run_root>`（不写出来给用户，自己内部记），以便用户追问明细时 Read `<run_root>/usage-summary.md`。

### 5. 阅读报告

Read `<run_root>/deep-search/report.md`（不读 HTML，HTML 是给用户看的，读 HTML 效率低）。

### 6. TaskUpdate 标 completed

### 7. 最终回复用户

给用户的回复包含三块：

**块 1：报告路径**（HTML 优先）

```
📄 调研报告（可视化版本，浏览器打开看更直观）：
   open <run_root>/deep-search/report.html      # mac
   xdg-open <run_root>/deep-search/report.html  # linux
```

按 `uname` / `$OSTYPE` 给出对应平台命令。

**块 2：核心结论**（用你自己的话，从 report.md 综合，**必须**附证据 URL / 关键原文 / 关键数字，不许编造）

**块 3：cost 一行总览**（P-USAGE-001）

```
📊 本次估算 ~$X.XXX USD（N 次调用 · M 个源 · K 次触发站点调用上限）
```

- N 次调用：本次 run 真实发出的请求总数
- M 个源：本次 run 实际调用过的 distinct backend / site 数
- K 次触发站点调用上限：被 `_http.py` 计数器拦下的请求；**K=0 时省略本段**

获取这一行最稳的方式：调

```bash
python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/finalize_usage.py <run_root> --one-line
```

返回值是一行字符串，可直接拼到回复末尾。

**绝对不要**在回复里写出 `<run_root>` 路径、详细 cost 拆分、`usage-summary.md` 字符串。

### 8. 用户追问处理

如果用户接着问「按 backend 拆开」/「细节」/「multimodal 调用占多少」等：

- → Read `<run_root>/usage-summary.md` 后呈现该文件内容（按用户问题剪裁）

如果用户接着问「我历史上总共花了多少」/「最近 10 次」：

- → 提示用户跑：
  ```
  ! python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/usage.py --last 10
  ```
- 不要主动 Bash 它（会进 context）

## 关键约束

- TaskCreate 必须在派发之前
- 同 turn 内若需派多个 subagent，必须一次性发起多个 Task 调用
- 不复述 report 全文；用你自己的话综合 + 证据挂回
- cost 总览**只一行**，不附路径、不展开拆分

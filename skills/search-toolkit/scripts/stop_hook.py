#!/usr/bin/env python3
"""Stop hook：扫 pending 目录，提示用户晋升 / 丢弃 / 暂留。

Claude Code Stop hook 协议：
- 由 Claude Code 在主 agent 工作告一段落时调用
- 通过 stdin 传入 hook input（JSON），通过 stdout 输出会被注入下一轮上下文的内容

详见 https://docs.claude.com/en/docs/claude-code/hooks（参考用，实际字段以本机版本为准）

约束（T-PENDING-001）：
- pending 为空 → 不输出（不打扰）
- pending 非空 → 输出简洁中文提示给用户
"""

from __future__ import annotations

import json
import sys

from lib import config


def main() -> int:
    # 读 hook 输入（不强依赖；当前不需要其中字段）
    try:
        _ = json.load(sys.stdin) if not sys.stdin.isatty() else {}
    except json.JSONDecodeError:
        pass

    pending = config.load_pending()
    total = sum(len(v) for v in pending.values())
    if total == 0:
        return 0

    lines = [
        "💡 Search Crew 学习区有新的候选规则：",
    ]
    if pending["routing"]:
        lines.append(f"- 路由候选 {len(pending['routing'])} 条")
        for p in pending["routing"][:5]:
            lines.append(f"  · {p.name}")
    if pending["adapters"]:
        lines.append(f"- 适配器候选 {len(pending['adapters'])} 条")
        for p in pending["adapters"][:5]:
            lines.append(f"  · {p.name}")
    lines.append("")
    lines.append("是否要：1) 晋升为长期规则  2) 丢弃  3) 暂留下次再问？")
    lines.append("（选「晋升」时由 AI 跑 promote.py 把它合并进 active 并记 changelog，不手改；")
    lines.append("  想自己看，文件在 ~/.config/search-crew/pending/）")

    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())

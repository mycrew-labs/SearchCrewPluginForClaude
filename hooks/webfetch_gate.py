#!/usr/bin/env python3
"""PreToolUse hook（matcher WebFetch）：把读 URL 纠回 web-page-fetch / fetch.py。

随 search-crew plugin 分发，是 web-page-fetch「双层防线」的第二层（动作点兜底）：
SKILL.md description 软引导漏触发时，在主 agent 实际调内置 WebFetch 的那一刻拦截。

分级（依据站点 → 抓取能力清单 site-fetch.txt，与 fetch.py 共用 lib/fetch_routing）：
- host 命中清单且能力 != builtin-webfetch → **每次硬拦**（deny）：这些站点内置 WebFetch
  必失败（强风控 / 虚拟滚动），reason 指明该用的能力与 fetch.py 命令。
- 其余 host → **本 session 首次软拦**（deny + 提示），retry 放行，为 fetch.py 的
  WEBFETCH_FALLBACK 回落留逃生舱。

fail-open：url 缺失 / 解析异常 / 本脚本任何错误 → 放行（exit 0、无输出），
绝不因 hook 自身故障阻断正常工具调用。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# 让 hook 能 import plugin 的共享 lib（scripts/ 为 import root）
_SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "search-toolkit" / "scripts"
sys.path.insert(0, str(_SCRIPTS))

_FLAG_PREFIX = "/tmp/.search-crew-webfetch-gate-"
_FETCH = "python3 $CLAUDE_PLUGIN_ROOT/skills/search-toolkit/scripts/fetch.py"


def _allow() -> None:
    """放行：PreToolUse 不输出 permissionDecision 即走正常权限流程。"""
    sys.exit(0)


def _deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }, ensure_ascii=False))
    sys.exit(0)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        _allow()
        return

    url = str((data.get("tool_input") or {}).get("url") or "").strip()
    if not url:
        _allow()
        return

    try:
        from lib import fetch_routing
        cap = fetch_routing.capability_for_url(url, fetch_routing.active_mapping())
    except Exception:
        _allow()  # 任何 import / 解析异常 → fail-open
        return

    # 硬拦：清单为该站点指定了「非内置 WebFetch」的能力
    if cap and cap != "builtin-webfetch":
        _deny(
            f"该站点（{url}）在 search-crew 的 site-fetch 清单中指定用 `{cap}` 抓取，"
            f"内置 WebFetch 对它无效（强风控 / 虚拟滚动长文档）。"
            f"MUST 改跑：{_FETCH} --real-browser <url>"
        )
        return

    # 软拦：本 session 首次拦一次，retry 放行（为 fetch.py 的 WEBFETCH_FALLBACK 回落留逃生舱）
    session_id = str(data.get("session_id") or "nosession")
    flag = Path(f"{_FLAG_PREFIX}{session_id}")
    if flag.exists():
        _allow()
        return
    try:
        flag.touch()
    except Exception:
        pass  # flag 写不了也不阻断；退化为每次软拦，仍 fail-safe
    _deny(
        f"读取 URL 优先用 search-crew 的 web-page-fetch：{_FETCH} <url>"
        f"（Jina 渲染 + raw 原文保真 + 反爬识别 + 可升级真实浏览器）。"
        f"若 fetch.py 已返回 WEBFETCH_FALLBACK 让你回落，请直接重试本次 WebFetch（会放行）。"
    )


if __name__ == "__main__":
    main()

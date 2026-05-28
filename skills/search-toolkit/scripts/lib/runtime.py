"""运行时上下文（session-id / run-root）。

I-DATA-001：run 产物落在 `/tmp/search-crew/<session_id>/`。
session_id 取自 Claude Code 注入的 `CLAUDE_CODE_SESSION_ID`（主会话，所有 subagent
共享）；Claude Code 不给 subagent 独立 id，所以**整个会话共用一个 run_root**，各
subagent 把产物写到 `<run_root>/<subagent>/` 子目录，usage 打点落 `<run_root>/usage.jsonl`，
两者同根。subagent **不要**自己编 session_id（会与打点分叉）——未拿到 target_dir 时
调 `run_paths.py --subagent <name>` 取规范目录。
T-SESSION-001：优先级 env → file marker → 时间戳兜底。
"""

from __future__ import annotations

import os
import pathlib
import secrets
import sys
import time


def get_session_id() -> str:
    """按 T-SESSION-001 的优先级返回 session-id。"""
    # 1. Claude Code 注入的环境变量
    for var in ("CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID"):
        v = os.environ.get(var, "").strip()
        if v:
            return v

    # 2. 文件 marker（plugin 可能放在 $CLAUDE_PLUGIN_ROOT/.session-marker）
    root = os.environ.get("CLAUDE_PLUGIN_ROOT", "").strip()
    if root:
        marker = pathlib.Path(root) / ".session-marker"
        if marker.exists():
            try:
                v = marker.read_text(encoding="utf-8").strip()
                if v:
                    return v
            except OSError:
                pass

    # 3. 时间戳 + 短随机串兜底
    fallback = f"{int(time.time())}-{secrets.token_hex(4)}"
    print(
        f"[runtime] 未拿到 CLAUDE_SESSION_ID，使用时间戳兜底: {fallback}",
        file=sys.stderr,
    )
    return fallback


def run_root(session_id: str | None = None) -> pathlib.Path:
    """返回本 run 的根目录 `/tmp/search-crew/<session_id>/`，并 mkdir。"""
    sid = session_id or get_session_id()
    p = pathlib.Path("/tmp/search-crew") / sid
    p.mkdir(parents=True, exist_ok=True)
    return p


def current_subagent() -> str:
    """从环境变量推断当前 subagent 名（用于打点）。

    Claude Code 未明确暴露此变量时返回 'unknown'；agent 在调脚本时可显式传
    `SEARCH_CREW_SUBAGENT` 环境变量覆盖。
    """
    for var in ("SEARCH_CREW_SUBAGENT", "CLAUDE_SUBAGENT_NAME"):
        v = os.environ.get(var, "").strip()
        if v:
            return v
    return "unknown"

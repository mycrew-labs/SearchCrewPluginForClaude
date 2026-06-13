#!/usr/bin/env python3
"""SessionStart hook：清本 plugin 的 webfetch 软拦 session flag。

随 search-crew plugin 分发，与 webfetch_gate.py 配套：SessionStart 在新启动 /
/clear / /resume / auto-compact 后触发——这些场景 session_id 不变但 AI 上下文已
重置或压缩，清掉旧 flag 让「本 session 首次软拦」重新生效。

fail-open：任何异常静默退出，不影响 session 启动。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_FLAG_PREFIX = "/tmp/.search-crew-webfetch-gate-"


def main() -> None:
    try:
        data = json.load(sys.stdin)
        session_id = str(data.get("session_id") or "nosession")
        flag = Path(f"{_FLAG_PREFIX}{session_id}")
        if flag.exists():
            flag.unlink()
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()

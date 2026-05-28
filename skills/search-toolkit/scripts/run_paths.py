#!/usr/bin/env python3
"""打印本次 run 的规范目录，供 subagent 在「未被上级指定 target_dir」时取用。

为什么需要它：Claude Code 只暴露一个 session id（主会话），所有 subagent 共享；
subagent 自己**拿不到**独立 id。若让 LLM 在 prompt 里「用自己的 session_id」拼目录，
它会编一个随机 id，导致产物目录与 usage 打点（用 runtime.get_session_id() = 主会话
id 落 usage.jsonl）分叉，finalize_usage 找不到打点 → cost 报 0。

本脚本用与打点**同一个** run_root（`runtime.run_root()`，基于 session id）算目录，
保证产物与打点同根。

用法：
    run_paths.py                  # 打印 run_root：/tmp/search-crew/<session>/
    run_paths.py --subagent fast-search
                                  # 打印 target_dir：/tmp/search-crew/<session>/fast-search/
"""

from __future__ import annotations

import argparse
import sys

from lib import runtime


def main() -> int:
    ap = argparse.ArgumentParser(description="打印本次 run 的规范目录")
    ap.add_argument("--subagent", default=None, help="子 agent 名；给了就打印 run_root/<subagent>/")
    args = ap.parse_args()

    root = runtime.run_root()
    if args.subagent:
        target = root / args.subagent
        target.mkdir(parents=True, exist_ok=True)
        print(str(target))
    else:
        print(str(root))
    return 0


if __name__ == "__main__":
    sys.exit(main())

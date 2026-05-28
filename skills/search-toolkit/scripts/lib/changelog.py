"""active 配置修改日志：~/.config/search-crew/changelog.log。

每次经脚本（seed / merge / promote）写入 active 都追加一条，带文件锁。
AI 永不手写本文件——只能经此辅助由脚本写入。

格式（每行一条，制表分隔）：
    <UTC ISO8601>\t<op>\t<target>\t<summary>\ttrigger=<trigger>
"""

from __future__ import annotations

import datetime
import fcntl
import pathlib

from . import config

_LOG_NAME = "changelog.log"


def changelog_path() -> pathlib.Path:
    return config.active_dir() / _LOG_NAME


def append_changelog(op: str, target: str, summary: str, trigger: str = "manual") -> None:
    """追加一条修改记录。active 目录必须已存在（调用方保证）。"""
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # summary / trigger 里若混入制表或换行会破坏单行格式，统一压成空格
    clean = lambda s: " ".join(str(s).split())
    line = f"{ts}\t{clean(op)}\t{clean(target)}\t{clean(summary)}\ttrigger={clean(trigger)}\n"
    path = changelog_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(line)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

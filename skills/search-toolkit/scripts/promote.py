#!/usr/bin/env python3
"""把一条 pending 候选晋升进 active（pending → active）。

这是 active 三个固定写入操作之一（另两个在 seed_user_config.py：seed / merge）。
晋升 MUST 经本脚本完成，禁止 AI 用编辑器手改 active。成功后删除已消费的 pending
文件并向 changelog 追加一条。

用法：
    promote.py <pending-file> [--trigger user-approved]

kind 由 pending 文件的父目录决定：
- pending/routing/*.yaml  → 文件内容是一个 topics 列表项，追加进 routing.yaml 的 topics:
- pending/adapters/*       → 整个文件移入 adapters/（重名报错不覆盖）
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

from lib import changelog, config
from lib.yaml_blocks import split_top_level_blocks

_TS_PREFIX = re.compile(r"^\d{8}T?\d{0,6}-")  # 形如 20260528T140000- 或 20260528-


def _slug_from_filename(name: str) -> str:
    """去掉文件名前缀的时间戳，留下 slug（含扩展名）。"""
    return _TS_PREFIX.sub("", name)


def _dedent_lines(text: str) -> list[str]:
    lines = text.splitlines()
    nonblank = [ln for ln in lines if ln.strip()]
    if not nonblank:
        return []
    common = min(len(ln) - len(ln.lstrip(" ")) for ln in nonblank)
    return [ln[common:] if ln.strip() else "" for ln in lines]


def _reindent(lines: list[str], spaces: int = 2) -> str:
    pad = " " * spaces
    out = [pad + ln if ln.strip() else "" for ln in lines]
    return "\n".join(out).rstrip("\n") + "\n"


def _topic_name(lines: list[str]) -> str:
    for ln in lines:
        m = re.match(r"^-?\s*name:\s*(\S+)", ln)
        if m:
            return m.group(1)
    return "?"


def _promote_routing(pending: pathlib.Path, trigger: str) -> int:
    routing = config.active_dir() / "routing.yaml"
    if not routing.exists():
        print(f"[promote] active routing.yaml 不存在：{routing}", file=sys.stderr)
        return 1

    item_lines = _dedent_lines(pending.read_text(encoding="utf-8"))
    if not item_lines or not item_lines[0].lstrip().startswith("- "):
        print(
            f"[promote] pending routing 片段格式不符（应是一个以 '- name:' 起头的 topics 列表项）：{pending}",
            file=sys.stderr,
        )
        return 1
    item_text = _reindent(item_lines, 2)
    name = _topic_name(item_lines)

    text = routing.read_text(encoding="utf-8")
    blocks = split_top_level_blocks(text)
    if "topics" not in blocks:
        print("[promote] routing.yaml 缺 topics: 段，无法定位插入点", file=sys.stderr)
        return 1

    tlines = blocks["topics"].splitlines(keepends=True)
    last = max((i for i, ln in enumerate(tlines) if ln.strip()), default=0)
    new_block = "".join(tlines[: last + 1]) + item_text + "".join(tlines[last + 1 :])
    blocks["topics"] = new_block
    routing.write_text("".join(blocks.values()), encoding="utf-8")

    changelog.append_changelog("promote", "routing.yaml", f"+topic:{name}", trigger=trigger)
    pending.unlink()
    print(f"[promote] 已晋升 topic:{name} 进 routing.yaml，删除 {pending.name}", file=sys.stderr)
    return 0


def _promote_adapter(pending: pathlib.Path, trigger: str) -> int:
    adapters = config.active_dir() / "adapters"
    adapters.mkdir(parents=True, exist_ok=True)
    target = adapters / _slug_from_filename(pending.name)
    if target.exists():
        print(f"[promote] adapters/ 已有同名文件，拒绝覆盖：{target.name}（请改名后重试）", file=sys.stderr)
        return 1
    pending.replace(target)
    changelog.append_changelog("promote", f"adapters/{target.name}", "+adapter", trigger=trigger)
    print(f"[promote] 已晋升 adapter 进 adapters/{target.name}", file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Search Crew pending → active 晋升")
    ap.add_argument("pending_file", help="pending/{routing,adapters}/ 下的候选文件路径")
    ap.add_argument("--trigger", default="user-approved", help="触发来源，写进 changelog")
    args = ap.parse_args()

    pending = pathlib.Path(args.pending_file).expanduser()
    if not pending.is_file():
        print(f"[promote] 文件不存在：{pending}", file=sys.stderr)
        return 1

    kind = pending.parent.name
    if kind == "routing":
        return _promote_routing(pending, args.trigger)
    if kind == "adapters":
        return _promote_adapter(pending, args.trigger)
    print(
        f"[promote] 无法判定 kind：pending 文件须在 pending/routing/ 或 pending/adapters/ 下，实际父目录={kind}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())

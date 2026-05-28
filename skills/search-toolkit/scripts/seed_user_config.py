#!/usr/bin/env python3
"""首次安装：把 plugin 内置 defaults/ 拷贝到 ~/.config/search-crew/。

约束（T-SEED-001）：
- 默认 if-not-exists 守卫，绝不覆盖已有文件
- 用文件锁防并发
- 多次调用幂等

`--merge` 子模式（borrow-smart-search-web-reader change 引入）：plugin 升级后
defaults/ 多出来的 YAML 顶层段（如新增的 `ai_summary:` / `call_cap:`），active
中缺失这些段时自动补齐；用户已有段一字不动。
"""

from __future__ import annotations

import argparse
import fcntl
import os
import pathlib
import re
import shutil
import sys

from lib import changelog, config
from lib.yaml_blocks import PREAMBLE_KEY, split_top_level_blocks


def _plugin_root() -> pathlib.Path:
    """从环境变量取 $CLAUDE_PLUGIN_ROOT；否则按本脚本路径推断。"""
    root = os.environ.get("CLAUDE_PLUGIN_ROOT", "").strip()
    if root:
        return pathlib.Path(root)
    # 本脚本位于 plugin/skills/search-toolkit/scripts/seed_user_config.py
    # 向上数 4 层到 plugin root
    return pathlib.Path(__file__).resolve().parents[3]


def _defaults_dir() -> pathlib.Path:
    return _plugin_root() / "defaults"


def _copy_if_not_exists(src: pathlib.Path, dst: pathlib.Path) -> int:
    """返回新增的文件数。"""
    count = 0
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for child in src.iterdir():
            count += _copy_if_not_exists(child, dst / child.name)
    else:
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            count += 1
    return count


def _missing_top_level_keys(src_path: pathlib.Path, dst_path: pathlib.Path) -> list[str]:
    """src 相对 dst 多出来的顶层 key（dst 缺失的段）。dst 不存在返回空（走普通 copy）。"""
    if not dst_path.exists():
        return []
    src_blocks = split_top_level_blocks(src_path.read_text(encoding="utf-8"))
    dst_blocks = split_top_level_blocks(dst_path.read_text(encoding="utf-8"))
    return [k for k in src_blocks if k != PREAMBLE_KEY and k not in dst_blocks]


def _merge_yaml_file(src_path: pathlib.Path, dst_path: pathlib.Path) -> list[str]:
    """把 src 里 dst 缺失的顶层 key 块追加到 dst 末尾。

    返回追加的 key 列表。dst 中已有的 key 一字不动；preamble 一字不动。
    """
    appended = _missing_top_level_keys(src_path, dst_path)
    if not appended:
        return []
    src_blocks = split_top_level_blocks(src_path.read_text(encoding="utf-8"))
    dst_text = dst_path.read_text(encoding="utf-8")
    new_text = dst_text if dst_text.endswith("\n") else dst_text + "\n"
    new_text += "\n# ---- 以下段由 seed_user_config.py --merge 从 plugin defaults 补齐 ----\n"
    new_text += "".join(src_blocks[k] for k in appended)
    dst_path.write_text(new_text, encoding="utf-8")
    return appended


def _do_merge(dry_run: bool = False, trigger: str = "manual") -> int:
    """扫 defaults/*.yaml，对每个 active 已存在的同名文件做顶层 key merge。

    dry_run=True 时只检测缺失段、不写盘、不记 changelog，stdout 输出机器可读结果。
    """
    src_dir = _defaults_dir()
    dst_dir = config.active_dir()
    if not dst_dir.exists():
        print(f"[seed --merge] active 不存在 {dst_dir}，请先跑普通 seed", file=sys.stderr)
        return 1

    if dry_run:
        any_missing = False
        for src in sorted(src_dir.glob("*.yaml")):
            missing = _missing_top_level_keys(src, dst_dir / src.name)
            if missing:
                any_missing = True
                # 机器可读：每行 "<file>\t<key1,key2>"
                print(f"{src.name}\t{','.join(missing)}")
        if not any_missing:
            print("[seed --merge --dry-run] 所有 active YAML 已与 defaults 同步", file=sys.stderr)
        return 0

    any_change = False
    for src in sorted(src_dir.glob("*.yaml")):
        dst = dst_dir / src.name
        added = _merge_yaml_file(src, dst)
        if added:
            any_change = True
            print(f"[seed --merge] {dst.name} 补齐 {len(added)} 段：{', '.join(added)}", file=sys.stderr)
            changelog.append_changelog(
                "merge", dst.name, "+" + " +".join(added), trigger=trigger
            )
        else:
            print(f"[seed --merge] {dst.name} 无需补齐", file=sys.stderr)
    if not any_change:
        print("[seed --merge] 所有 active YAML 已与 defaults 同步", file=sys.stderr)
    return 0


_VALID_FAST_DEFAULT = ("auto", "grok", "gemini", "doubao")


def _set_fast_default(value: str, trigger: str = "setup") -> int:
    """seed 期初始化配置：写 active routing.yaml 的 ai_summary.fast_default（不手改、走脚本）。"""
    if value not in _VALID_FAST_DEFAULT:
        print(f"[set-fast-default] 非法值 '{value}'，须是 {_VALID_FAST_DEFAULT}", file=sys.stderr)
        return 1
    routing = config.active_dir() / "routing.yaml"
    if not routing.exists():
        print(f"[set-fast-default] routing.yaml 不存在：{routing}（请先 seed）", file=sys.stderr)
        return 1
    blocks = split_top_level_blocks(routing.read_text(encoding="utf-8"))
    if "ai_summary" not in blocks:
        print("[set-fast-default] routing.yaml 缺 ai_summary 段", file=sys.stderr)
        return 1
    lines = blocks["ai_summary"].splitlines(keepends=True)
    new_line = f"  fast_default: {value}\n"
    for i, ln in enumerate(lines):
        if re.match(r"^\s{2}fast_default:\s*", ln):
            lines[i] = new_line
            break
    else:
        lines.insert(1, new_line)  # 紧跟 `ai_summary:` 头一行后插入
    blocks["ai_summary"] = "".join(lines)
    routing.write_text("".join(blocks.values()), encoding="utf-8")
    changelog.append_changelog("set-fast-default", "routing.yaml", f"ai_summary.fast_default={value}", trigger=trigger)
    print(f"[set-fast-default] ai_summary.fast_default = {value}", file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Search Crew seed_user_config")
    ap.add_argument(
        "--set-fast-default",
        choices=list(_VALID_FAST_DEFAULT),
        default=None,
        help="seed 期初始化配置：设 /search-fast 默认引擎（写 ai_summary.fast_default）",
    )
    ap.add_argument(
        "--merge",
        action="store_true",
        help="为已存在的 active YAML 补齐 defaults 中新增的顶层段（用户已有段一字不动）",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="配合 --merge：只检测 active 缺哪些顶层段、不写盘（stdout 输出 '<file>\\t<keys>'）",
    )
    ap.add_argument(
        "--trigger",
        default="manual",
        help="标注本次写入的触发来源，写进 changelog（如 setup / first-install）",
    )
    args = ap.parse_args()

    if args.set_fast_default:
        trigger = args.trigger if args.trigger != "manual" else "setup"
        return _set_fast_default(args.set_fast_default, trigger=trigger)

    if args.merge:
        return _do_merge(dry_run=args.dry_run, trigger=args.trigger)

    src = _defaults_dir()
    if not src.exists():
        print(f"[seed] defaults/ 不存在：{src}", file=sys.stderr)
        return 1

    dst = config.active_dir()
    dst.mkdir(parents=True, exist_ok=True)

    # 文件锁防并发
    lock_path = dst / ".seed.lock"
    with open(lock_path, "w", encoding="utf-8") as lock_f:
        try:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
            new_count = _copy_if_not_exists(src, dst)
            print(f"[seed] 从 {src} → {dst}，新增 {new_count} 个文件", file=sys.stderr)
        finally:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)

    # 标记完成
    (dst / ".seeded").touch()
    if new_count:
        trigger = args.trigger if args.trigger != "manual" else "first-install"
        changelog.append_changelog("seed", "(init)", f"{new_count} files", trigger=trigger)
    return 0


if __name__ == "__main__":
    sys.exit(main())

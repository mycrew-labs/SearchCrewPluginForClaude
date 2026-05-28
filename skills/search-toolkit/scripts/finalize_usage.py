#!/usr/bin/env python3
"""聚合 <run_root>/usage.jsonl → 生成 usage-summary.md + 追加 runs.jsonl。

CLI:
  python3 finalize_usage.py <run_root>                     # 全局 summary
  python3 finalize_usage.py --subagent <name> <run_root>   # 单 subagent 切片

输出文件：
  <run_root>/usage-summary.md         （全局，整体调研一行总览的数据源）
  <run_root>/<subagent>/usage-summary.md（切片，subagent 自身使用）

副作用：
  ~/.local/state/search-crew/runs.jsonl 末尾追加一行（仅全局模式）
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import sys
from collections import defaultdict
from typing import Any

from lib import config


def _utc_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-4] + "Z"


def _load_records(jsonl: pathlib.Path) -> list[dict[str, Any]]:
    if not jsonl.exists():
        return []
    out = []
    for line in jsonl.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    # call_cap_exceeded 记录单独统计，不计入「调用总数」
    real_records = [r for r in records if r.get("status") != "call_cap_exceeded"]
    skipped_records = [r for r in records if r.get("status") == "call_cap_exceeded"]

    total_calls = len(real_records)
    total_cost = 0.0
    by_backend: dict[str, dict[str, float]] = defaultdict(lambda: {"calls": 0, "cost": 0.0})
    by_subagent: dict[str, dict[str, float]] = defaultdict(lambda: {"calls": 0, "cost": 0.0})
    unknown_backends: set[str] = set()
    # 搜索摘要：{backend -> [queries]}
    queries_by_backend: dict[str, list[str]] = defaultdict(list)
    distinct_backends: set[str] = set()

    for r in real_records:
        backend = r.get("backend", "unknown")
        subagent = r.get("subagent", "unknown")
        cost = r.get("cost_estimate_usd")
        source = r.get("pricing_source", "unknown")
        query = (r.get("query") or "").strip()

        by_backend[backend]["calls"] += 1
        by_subagent[subagent]["calls"] += 1
        distinct_backends.add(backend)
        if query:
            queries_by_backend[backend].append(query)

        if isinstance(cost, (int, float)):
            by_backend[backend]["cost"] += cost
            by_subagent[subagent]["cost"] += cost
            total_cost += cost
        elif source == "unknown":
            unknown_backends.add(f"{backend}:{r.get('endpoint', '')}")

    # 已跳过（call_cap_exceeded）
    skipped_by_backend: dict[str, list[str]] = defaultdict(list)
    for r in skipped_records:
        b = r.get("backend", "unknown")
        q = (r.get("query") or "").strip()
        skipped_by_backend[b].append(q)

    completeness = "full"
    if unknown_backends and total_calls > 0:
        completeness = "partial" if len(unknown_backends) < total_calls else "none"

    return {
        "calls": total_calls,
        "cost_estimate_usd": round(total_cost, 4),
        "by_backend": {k: {"calls": v["calls"], "cost": round(v["cost"], 4)} for k, v in by_backend.items()},
        "by_subagent": {k: {"calls": v["calls"], "cost": round(v["cost"], 4)} for k, v in by_subagent.items()},
        "pricing_completeness": completeness,
        "unknown_backends": sorted(unknown_backends),
        # 搜索摘要素材
        "queries_by_backend": {k: _dedup_preserve_order(v) for k, v in queries_by_backend.items()},
        "skipped_by_backend": {k: _dedup_preserve_order(v) for k, v in skipped_by_backend.items()},
        "distinct_source_count": len(distinct_backends),
        "skipped_count": len(skipped_records),
    }


def _dedup_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        if it and it not in seen:
            seen.add(it)
            out.append(it)
    return out


def _render_md(agg: dict[str, Any], scope: str, run_id: str) -> str:
    completeness_label = {
        "full": "单价完整",
        "partial": "部分缺失",
        "none": "全部未知",
    }.get(agg["pricing_completeness"], agg["pricing_completeness"])

    lines: list[str] = []
    lines.append(f"# 本次使用 · {scope}\n")
    lines.append(f"- run_id: {run_id}")
    lines.append(f"- 生成时间: {_utc_iso()}")
    lines.append(f"- 调用总数: {agg['calls']}")
    lines.append(f"- 估算合计: ~${agg['cost_estimate_usd']:.4f} USD（**估算**，可能与官方账单有误差）")
    lines.append(f"- 单价完整度: {completeness_label}")
    lines.append("")

    if agg["by_backend"]:
        lines.append("## 按 backend\n")
        lines.append("| Backend | 次数 | 估算 cost |")
        lines.append("|---|---:|---:|")
        for b, v in sorted(agg["by_backend"].items(), key=lambda x: -x[1]["cost"]):
            lines.append(f"| {b} | {v['calls']} | ~${v['cost']:.4f} |")
        lines.append("")

    if agg["by_subagent"]:
        lines.append("## 按 subagent\n")
        lines.append("| Subagent | 次数 | 估算 cost |")
        lines.append("|---|---:|---:|")
        for s, v in sorted(agg["by_subagent"].items(), key=lambda x: -x[1]["cost"]):
            lines.append(f"| {s} | {v['calls']} | ~${v['cost']:.4f} |")
        lines.append("")

    if agg["unknown_backends"]:
        lines.append("## ⚠️ 单价未知的调用（未计入合计）\n")
        for u in agg["unknown_backends"]:
            lines.append(f"- {u}")
        lines.append("")

    # 搜索摘要段（循证传递的过程层信号；用户主对话不带，CLI 可查 / 直接 Read）
    queries_by_backend = agg.get("queries_by_backend") or {}
    skipped_by_backend = agg.get("skipped_by_backend") or {}
    if queries_by_backend or skipped_by_backend:
        lines.append("## 搜索摘要\n")
        for backend, queries in sorted(queries_by_backend.items()):
            term_str = "；".join(queries) if queries else "（未记录查询词）"
            lines.append(
                f"- 网站：{backend} | 查询词：{term_str} | 次数：{agg['by_backend'][backend]['calls']}"
            )
        for backend, queries in sorted(skipped_by_backend.items()):
            term_str = "；".join(q for q in queries if q) or "（未记录查询词）"
            lines.append(f"- 已跳过：{backend}，原因：触发站点调用上限（尝试查询词：{term_str}）")
        lines.append("")

    lines.append("> 详细打点见 `usage.jsonl`（jsonl 一行一条）。")
    return "\n".join(lines)


def _render_one_line(agg: dict[str, Any]) -> str:
    """主 agent 用的一行 cost 总览：『N 次调用 · M 个源 · K 次触发站点调用上限』。"""
    calls = agg["calls"]
    cost = agg["cost_estimate_usd"]
    sources = agg.get("distinct_source_count", 0)
    skipped = agg.get("skipped_count", 0)

    parts = [f"{calls} 次调用", f"{sources} 个源"]
    if skipped > 0:
        parts.append(f"{skipped} 次触发站点调用上限")
    detail = " · ".join(parts)
    return f"📊 本次估算 ~${cost:.4f} USD（{detail}）"


def main() -> int:
    ap = argparse.ArgumentParser(description="Search Crew usage 聚合")
    ap.add_argument("run_root", type=pathlib.Path)
    ap.add_argument("--subagent", default=None, help="只聚合本 subagent 的切片")
    ap.add_argument(
        "--one-line",
        action="store_true",
        help="只输出主 agent 用的一行 cost 总览（不写文件）",
    )
    args = ap.parse_args()

    run_root: pathlib.Path = args.run_root.resolve()
    if not run_root.exists():
        print(f"run_root 不存在: {run_root}", file=sys.stderr)
        return 1

    if args.one_line:
        records = _load_records(run_root / "usage.jsonl")
        if args.subagent:  # 切片：只统计本 subagent，避免会话级 run_root 把整会话累计进来
            records = [r for r in records if r.get("subagent") == args.subagent]
        agg = _aggregate(records)
        print(_render_one_line(agg))
        return 0

    all_records = _load_records(run_root / "usage.jsonl")
    if args.subagent:
        records = [r for r in all_records if r.get("subagent") == args.subagent]
        agg = _aggregate(records)
        md = _render_md(agg, scope=args.subagent, run_id=run_root.name)
        out_path = run_root / args.subagent / "usage-summary.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md, encoding="utf-8")
        print(f"[finalize_usage] wrote {out_path}", file=sys.stderr)
        return 0

    # 全局
    agg = _aggregate(all_records)
    md = _render_md(agg, scope="全局", run_id=run_root.name)
    out_path = run_root / "usage-summary.md"
    out_path.write_text(md, encoding="utf-8")

    # 追加 runs.jsonl
    run_record = {
        "run_id": run_root.name,
        "ended_at": _utc_iso(),
        "totals": agg,
    }
    runs_path = config.state_dir() / "runs.jsonl"
    with open(runs_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(run_record, ensure_ascii=False) + "\n")

    print(f"[finalize_usage] wrote {out_path} + appended {runs_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

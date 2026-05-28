"""TC-USAGE-001 / 002：finalize_usage.py 聚合 + 追加 runs.jsonl。"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "skills" / "search-toolkit" / "scripts"


class TestFinalizeUsage(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.run_root = pathlib.Path(self.tmp.name) / "run-xxx"
        self.run_root.mkdir()
        self.state = pathlib.Path(self.tmp.name) / "state"
        self.state.mkdir()
        os.environ["XDG_STATE_HOME"] = str(self.state)
        os.environ["XDG_CONFIG_HOME"] = self.tmp.name  # 避免污染真实 config

    def tearDown(self) -> None:
        os.environ.pop("XDG_STATE_HOME", None)
        os.environ.pop("XDG_CONFIG_HOME", None)
        self.tmp.cleanup()

    def _write_usage(self, records: list[dict]) -> None:
        with open(self.run_root / "usage.jsonl", "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "finalize_usage.py"), *args],
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ},
        )

    def test_global_summary_basic(self) -> None:
        self._write_usage(
            [
                {"ts": "2026-05-21T10:00:00Z", "run_id": "run-xxx", "subagent": "fast-search", "backend": "jina", "endpoint": "search", "status": 200, "latency_ms": 100, "cost_estimate_usd": 0.0015, "pricing_source": "active"},
                {"ts": "2026-05-21T10:00:01Z", "run_id": "run-xxx", "subagent": "fast-search", "backend": "jina", "endpoint": "reader", "status": 200, "latency_ms": 200, "cost_estimate_usd": 0.0007, "pricing_source": "active"},
                {"ts": "2026-05-21T10:00:02Z", "run_id": "run-xxx", "subagent": "site-search", "backend": "serper", "endpoint": "search", "status": 200, "latency_ms": 150, "cost_estimate_usd": 0.001, "pricing_source": "active"},
            ]
        )
        self._run(str(self.run_root))
        summary = (self.run_root / "usage-summary.md").read_text(encoding="utf-8")
        self.assertIn("调用总数: 3", summary)
        self.assertIn("jina", summary)
        self.assertIn("serper", summary)
        self.assertIn("fast-search", summary)
        self.assertIn("site-search", summary)
        # runs.jsonl 已追加一行
        runs = (self.state / "search-crew" / "runs.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(runs), 1)
        rec = json.loads(runs[0])
        self.assertEqual(rec["run_id"], "run-xxx")
        self.assertEqual(rec["totals"]["calls"], 3)

    def test_unknown_pricing_marked(self) -> None:
        self._write_usage(
            [
                {"ts": "2026-05-21T10:00:00Z", "run_id": "run-xxx", "subagent": "fast-search", "backend": "brave", "endpoint": "search", "status": 200, "latency_ms": 100, "cost_estimate_usd": None, "pricing_source": "unknown"},
            ]
        )
        self._run(str(self.run_root))
        summary = (self.run_root / "usage-summary.md").read_text(encoding="utf-8")
        self.assertIn("⚠️", summary)
        self.assertIn("brave:search", summary)

    def test_subagent_slice(self) -> None:
        self._write_usage(
            [
                {"ts": "2026-05-21T10:00:00Z", "run_id": "run-xxx", "subagent": "fast-search", "backend": "jina", "endpoint": "search", "status": 200, "latency_ms": 100, "cost_estimate_usd": 0.001, "pricing_source": "active"},
                {"ts": "2026-05-21T10:00:01Z", "run_id": "run-xxx", "subagent": "deep-search", "backend": "jina", "endpoint": "search", "status": 200, "latency_ms": 100, "cost_estimate_usd": 0.002, "pricing_source": "active"},
            ]
        )
        self._run("--subagent", "fast-search", str(self.run_root))
        slice_file = self.run_root / "fast-search" / "usage-summary.md"
        self.assertTrue(slice_file.exists())
        text = slice_file.read_text(encoding="utf-8")
        self.assertIn("fast-search", text)
        self.assertIn("调用总数: 1", text)

    def test_one_line_honors_subagent_filter(self) -> None:
        """--one-line + --subagent 只统计该 subagent（会话级 run_root 不被整会话污染）。"""
        self._write_usage(
            [
                {"ts": "2026-05-21T10:00:00Z", "run_id": "run-xxx", "subagent": "fast-search", "backend": "jina", "endpoint": "search", "status": 200, "latency_ms": 100, "cost_estimate_usd": 0.001, "pricing_source": "active"},
                {"ts": "2026-05-21T10:00:01Z", "run_id": "run-xxx", "subagent": "deep-search", "backend": "grok", "endpoint": "responses", "status": 200, "latency_ms": 100, "cost_estimate_usd": 0.05, "pricing_source": "active"},
                {"ts": "2026-05-21T10:00:02Z", "run_id": "run-xxx", "subagent": "deep-search", "backend": "jina", "endpoint": "search", "status": "call_cap_exceeded", "latency_ms": 0, "cost_estimate_usd": None, "pricing_source": "active"},
            ]
        )
        whole = self._run(str(self.run_root), "--one-line").stdout
        self.assertIn("2 次调用", whole)
        self.assertIn("触发站点调用上限", whole)
        sliced = self._run(str(self.run_root), "--subagent", "fast-search", "--one-line").stdout
        self.assertIn("1 次调用", sliced)
        self.assertIn("0.0010", sliced)
        self.assertNotIn("触发站点调用上限", sliced)


if __name__ == "__main__":
    unittest.main()

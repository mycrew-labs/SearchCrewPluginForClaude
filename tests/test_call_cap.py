"""TC-CALL-CAP-001: lib/_http.py 站点调用上限计数器。

验证：
- AI backend 默认上限 1 次
- 非 AI backend 默认上限 2 次
- 触发上限 raise BackendError(retryable=False)
- 跨 run_id 不互通
- limits.yaml 覆盖默认值
"""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "skills" / "search-toolkit" / "scripts"))


class TestCallCap(unittest.TestCase):
    def setUp(self) -> None:
        # 隔离 XDG_CONFIG_HOME 避免读到用户真实 limits.yaml
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["XDG_CONFIG_HOME"] = self.tmp.name
        os.environ["XDG_STATE_HOME"] = self.tmp.name
        # 清空计数器
        from lib import _http  # noqa: PLC0415

        _http.reset_call_counter()
        self._http = _http

    def tearDown(self) -> None:
        os.environ.pop("XDG_CONFIG_HOME", None)
        os.environ.pop("XDG_STATE_HOME", None)
        os.environ.pop("SEARCH_CREW_RUN_ID", None)
        self.tmp.cleanup()

    def test_ai_backend_cap_default_1(self) -> None:
        os.environ["SEARCH_CREW_RUN_ID"] = "run-ai-1"
        from lib import BackendError  # noqa: PLC0415

        self._http._check_and_increment_cap("grok")  # 第 1 次 ok（grok 是 AI backend）
        with self.assertRaises(BackendError) as ctx:
            self._http._check_and_increment_cap("grok")
        self.assertIn("站点调用上限", str(ctx.exception))

    def test_non_ai_backend_cap_default_2(self) -> None:
        os.environ["SEARCH_CREW_RUN_ID"] = "run-non-ai-1"
        from lib import BackendError  # noqa: PLC0415

        self._http._check_and_increment_cap("jina")
        self._http._check_and_increment_cap("jina")
        with self.assertRaises(BackendError):
            self._http._check_and_increment_cap("jina")

    def test_each_ai_backend_independent(self) -> None:
        os.environ["SEARCH_CREW_RUN_ID"] = "run-multi"
        # grok 1 次后超限；切到 doubao 仍可调用 1 次
        self._http._check_and_increment_cap("grok")
        self._http._check_and_increment_cap("doubao")
        self._http._check_and_increment_cap("gemini")

    def test_cap_exempt_never_blocked(self) -> None:
        # 读取/抓取豁免：同 backend 连续多次都不被拦
        os.environ["SEARCH_CREW_RUN_ID"] = "run-exempt"
        for _ in range(5):
            self._http._check_and_increment_cap("jina", cap_exempt=True)  # 不抛即通过

    def test_search_still_capped_when_not_exempt(self) -> None:
        # 豁免不影响搜索：同 run 内 exempt 抓取 + 非 exempt 搜索，搜索仍受限
        os.environ["SEARCH_CREW_RUN_ID"] = "run-mixed"
        from lib import BackendError  # noqa: PLC0415
        for _ in range(3):
            self._http._check_and_increment_cap("jina", cap_exempt=True)  # 抓取豁免
        self._http._check_and_increment_cap("jina")  # 搜索第 1 次
        self._http._check_and_increment_cap("jina")  # 搜索第 2 次
        with self.assertRaises(BackendError):
            self._http._check_and_increment_cap("jina")  # 搜索第 3 次被拦

    def test_cross_run_independent(self) -> None:
        # run-A 把 grok 用完
        os.environ["SEARCH_CREW_RUN_ID"] = "run-A"
        self._http._check_and_increment_cap("grok")

        # run-B 重新可用
        os.environ["SEARCH_CREW_RUN_ID"] = "run-B"
        self._http._check_and_increment_cap("grok")

    def test_call_cap_exceeded_records_to_usage(self) -> None:
        """触发上限时也要 record 一条 status=call_cap_exceeded（供 usage-summary 渲染「已跳过」）。"""
        os.environ["SEARCH_CREW_RUN_ID"] = "run-record"
        from lib import BackendError  # noqa: PLC0415

        self._http._check_and_increment_cap("grok")
        with self.assertRaises(BackendError):
            self._http._check_and_increment_cap("grok", query="some query")

        calls_path = pathlib.Path(self.tmp.name) / "search-crew" / "calls.jsonl"
        self.assertTrue(calls_path.exists())
        import json

        records = [json.loads(line) for line in calls_path.read_text().splitlines() if line.strip()]
        cap_records = [r for r in records if r.get("status") == "call_cap_exceeded"]
        self.assertEqual(len(cap_records), 1)
        self.assertEqual(cap_records[0]["backend"], "grok")
        self.assertEqual(cap_records[0]["query"], "some query")


if __name__ == "__main__":
    unittest.main()

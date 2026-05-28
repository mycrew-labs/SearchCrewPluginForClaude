"""ai_search.py：AI 综述快答的选源 / 输出 / 回落。"""

from __future__ import annotations

import io
import json
import pathlib
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "skills" / "search-toolkit" / "scripts"))

import ai_search  # noqa: E402


def _run(argv):
    buf = io.StringIO()
    with mock.patch.object(sys, "argv", ["ai_search.py", *argv]):
        with redirect_stdout(buf):
            ai_search.main()
    return json.loads(buf.getvalue())


class TestAiSearch(unittest.TestCase):
    def test_chinese_prefers_doubao(self):
        # doubao 可用 → 中文 query 应选 doubao
        fake_doubao = mock.Mock(); fake_doubao.is_available.return_value = True
        with mock.patch.dict(ai_search.ai_summary.AI_BACKEND_MODULES, {"doubao": fake_doubao}):
            with mock.patch.object(ai_search.ai_summary, "pick_backend", side_effect=lambda x: x) as pick:
                with mock.patch.object(ai_search.ai_summary, "resolve_model", return_value="m"):
                    with mock.patch.object(ai_search.ai_summary, "run_ai", return_value={"backend": "doubao", "summary": "综述", "citations": ["u"]}):
                        out = _run(["--query", "国产新能源车推荐"])
        pick.assert_called_with("doubao")  # 中文 → 显式传 doubao
        self.assertEqual(out["backend"], "doubao")
        self.assertEqual(out["summary"], "综述")

    def test_english_uses_default_order(self):
        with mock.patch.object(ai_search.ai_summary, "pick_backend", return_value="grok") as pick:
            with mock.patch.object(ai_search.ai_summary, "resolve_model", return_value="m"):
                with mock.patch.object(ai_search.ai_summary, "run_ai", return_value={"backend": "grok", "summary": "s", "citations": []}):
                    out = _run(["--query", "open source vector db"])
        pick.assert_called_with(None)  # 英文 → 不强制，交默认 selection_order
        self.assertEqual(out["backend"], "grok")

    def test_no_ai_available_fallback(self):
        with mock.patch.object(ai_search.ai_summary, "pick_backend", return_value=None):
            out = _run(["--query", "anything"])
        self.assertIsNone(out["backend"])
        self.assertEqual(out["fallback"], "WEBSEARCH_FALLBACK")


if __name__ == "__main__":
    unittest.main()

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
                    with mock.patch.object(ai_search.ai_summary, "run_ai", return_value={"backend": "doubao", "summary": "综述", "citations": [{"url": "u"}]}):
                        out = _run(["--query", "国产新能源车推荐"])
        pick.assert_called_with("doubao")  # 中文 → 显式传 doubao
        self.assertEqual(out["backend"], "doubao")
        self.assertEqual(out["summary"], "综述")
        self.assertEqual(out["calls"], 1)
        self.assertIn("1 次调用 · doubao", out["cost_line"])  # 自报 cost 一行（不走 finalize_usage）

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


class TestFastDefault(unittest.TestCase):
    def _avail(self, *names):
        mods = {}
        for n in ("grok", "gemini", "doubao"):
            m = mock.Mock(); m.is_available.return_value = (n in names); mods[n] = m
        return mods

    def test_fast_default_forces_backend(self):
        with mock.patch.object(ai_search.ai_summary, "ai_summary_cfg", return_value={"fast_default": "gemini"}):
            with mock.patch.dict(ai_search.ai_summary.AI_BACKEND_MODULES, self._avail("grok", "gemini", "doubao")):
                # 中文 query 也应被 fast_default 强制成 gemini
                self.assertEqual(ai_search._lang_preferred_backend("国产新能源车"), "gemini")

    def test_auto_falls_to_language(self):
        with mock.patch.object(ai_search.ai_summary, "ai_summary_cfg", return_value={"fast_default": "auto"}):
            with mock.patch.dict(ai_search.ai_summary.AI_BACKEND_MODULES, self._avail("grok", "gemini", "doubao")):
                self.assertEqual(ai_search._lang_preferred_backend("国产新能源车"), "doubao")  # 中文→doubao
                self.assertIsNone(ai_search._lang_preferred_backend("open source db"))  # 英文→交 selection_order

    def test_fast_default_unavailable_falls_back(self):
        with mock.patch.object(ai_search.ai_summary, "ai_summary_cfg", return_value={"fast_default": "gemini"}):
            with mock.patch.dict(ai_search.ai_summary.AI_BACKEND_MODULES, self._avail("doubao")):  # gemini 不可用
                self.assertEqual(ai_search._lang_preferred_backend("国产新能源车"), "doubao")  # 回落语言
                self.assertIsNone(ai_search._lang_preferred_backend("open source db"))


class TestRenderCitations(unittest.TestCase):
    def test_with_offsets_inserts_footnotes(self):
        summary = "PostgreSQL 很强。Redis 很快。"
        # end_index 指向各句末（按字符数）
        cits = [
            {"url": "https://pg.example", "title": "PG", "end_index": len("PostgreSQL 很强。")},
            {"url": "https://redis.example", "title": "Redis", "end_index": len(summary)},
        ]
        cited, sources, has = ai_search._render_citations(summary, cits)
        self.assertTrue(has)
        self.assertIn("[1]", cited)
        self.assertIn("[2]", cited)
        # [1] 在 [2] 之前出现
        self.assertLess(cited.index("[1]"), cited.index("[2]"))
        self.assertEqual([s["n"] for s in sources], [1, 2])
        self.assertEqual(sources[0]["url"], "https://pg.example")

    def test_no_offsets_returns_plain_list(self):
        summary = "一段综述。"
        cits = [
            {"url": "https://a", "title": "A", "site_name": "站A", "publish_time": "2026-05"},
            {"url": "https://b", "title": "B"},
        ]
        cited, sources, has = ai_search._render_citations(summary, cits)
        self.assertFalse(has)
        self.assertEqual(cited, summary)  # 无偏移 → 正文不动
        self.assertNotIn("[1]", cited)
        self.assertEqual(sources[0]["site_name"], "站A")  # 富元数据保留

    def test_empty_citations(self):
        _cited, sources, has = ai_search._render_citations("x", [])
        self.assertFalse(has)
        self.assertEqual(sources, [])


if __name__ == "__main__":
    unittest.main()

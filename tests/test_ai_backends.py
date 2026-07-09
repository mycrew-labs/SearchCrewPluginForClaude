"""TC-AI-BACKEND-001: 三家 AI 综述 backend 的响应解析。

mock urllib.request.urlopen，验证：
- grok：解析顶层 citations[]
- ark（火山方舟）：解析 message.annotations[].url_citation
- gemini：解析 candidates[].groundingMetadata.groundingChunks[].web.uri
- 三家共用 make_envelope 统一返回 {backend, summary, citations, results}
"""

from __future__ import annotations

import io
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "skills" / "search-toolkit" / "scripts"))


def _make_response(body: dict) -> mock.MagicMock:
    """构造一个能被 urlopen 上下文管理器返回的 mock。"""
    resp = mock.MagicMock()
    resp.status = 200
    resp.read.return_value = json.dumps(body).encode("utf-8")
    cm = mock.MagicMock()
    cm.__enter__.return_value = resp
    cm.__exit__.return_value = False
    return cm


class TestAIBackends(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["XDG_CONFIG_HOME"] = self.tmp.name
        os.environ["XDG_STATE_HOME"] = self.tmp.name
        os.environ["SEARCH_CREW_RUN_ID"] = "test-ai-backend-run"
        from lib import _http  # noqa: PLC0415

        _http.reset_call_counter()

    def tearDown(self) -> None:
        for k in ("XDG_CONFIG_HOME", "XDG_STATE_HOME", "SEARCH_CREW_RUN_ID",
                  "GROK_API_KEY", "DOUBAO_API_KEY", "GEMINI_API_KEY"):
            os.environ.pop(k, None)
        self.tmp.cleanup()

    def _responses_api_body(self, text: str, urls: list[str]) -> dict:
        """构造 OpenAI 风格 Responses API 响应（xAI / 火山方舟共用结构）。"""
        return {
            "status": "completed",
            "output": [
                {"type": "reasoning", "summary": [], "status": "completed"},
                {"type": "web_search_call", "status": "completed", "action": {"type": "search"}},
                {
                    "type": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": [
                        {
                            "type": "output_text",
                            "text": text,
                            "annotations": [
                                {"type": "url_citation", "url": u, "title": f"src{i}"}
                                for i, u in enumerate(urls)
                            ],
                        }
                    ],
                },
            ],
        }

    def test_grok_parses_responses_api(self) -> None:
        os.environ["GROK_API_KEY"] = "test-key"
        from lib.backends import ai_grok  # noqa: PLC0415

        fake_resp = self._responses_api_body(
            "grok 综述正文", ["https://example.com/a", "https://example.com/b"]
        )
        with mock.patch("urllib.request.urlopen", return_value=_make_response(fake_resp)) as urlopen:
            envelope = ai_grok.search("hello", model="grok-4.3", reasoning_effort="low")
        self.assertEqual(envelope["backend"], "grok")
        self.assertEqual(envelope["summary"], "grok 综述正文")
        req = urlopen.call_args.args[0]
        body = json.loads(req.data.decode("utf-8"))
        self.assertEqual(body["model"], "grok-4.3")
        self.assertEqual(body["reasoning"], {"effort": "low"})
        urls = {c["url"] for c in envelope["citations"]}
        self.assertEqual(urls, {"https://example.com/a", "https://example.com/b"})
        # results 字段与 jina/serper 同 schema
        self.assertEqual(len(envelope["results"]), 2)
        self.assertIn("title", envelope["results"][0])
        self.assertIn("url", envelope["results"][0])

    def test_doubao_parses_responses_api(self) -> None:
        os.environ["DOUBAO_API_KEY"] = "test-key"
        from lib.backends import ai_doubao  # noqa: PLC0415

        fake_resp = self._responses_api_body("doubao 综述正文", ["https://zhihu.com/q/1"])
        with mock.patch("urllib.request.urlopen", return_value=_make_response(fake_resp)):
            envelope = ai_doubao.search("hello", model="doubao-seed-2-0-pro-260215")
        self.assertEqual(envelope["backend"], "doubao")
        self.assertEqual(envelope["summary"], "doubao 综述正文")
        self.assertEqual(len(envelope["citations"]), 1)
        self.assertEqual(envelope["citations"][0]["url"], "https://zhihu.com/q/1")

    def test_gemini_parses_grounding_chunks(self) -> None:
        os.environ["GEMINI_API_KEY"] = "test-key"
        from lib.backends import ai_gemini  # noqa: PLC0415

        fake_resp = {
            "candidates": [
                {
                    "content": {"parts": [{"text": "gemini 综述正文"}]},
                    "groundingMetadata": {
                        "groundingChunks": [
                            {"web": {"uri": "https://wiki/x", "title": "Wiki X"}},
                            {"web": {"uri": "https://blog/y", "title": "Blog Y"}},
                        ]
                    },
                }
            ]
        }
        with mock.patch("urllib.request.urlopen", return_value=_make_response(fake_resp)):
            envelope = ai_gemini.search("hello", model="gemini-2.5-flash-lite")
        self.assertEqual(envelope["backend"], "gemini")
        self.assertEqual(envelope["summary"], "gemini 综述正文")
        urls = {c["url"] for c in envelope["citations"]}
        self.assertEqual(urls, {"https://wiki/x", "https://blog/y"})

    def test_missing_key_raises(self) -> None:
        # 不设置任何 key
        from lib import BackendError  # noqa: PLC0415
        from lib.backends import ai_grok  # noqa: PLC0415

        with self.assertRaises(BackendError) as ctx:
            ai_grok.search("hello", model="grok-4.3")
        self.assertIn("GROK_API_KEY", str(ctx.exception))

    def test_missing_model_raises(self) -> None:
        os.environ["GROK_API_KEY"] = "test-key"
        from lib import BackendError  # noqa: PLC0415
        from lib.backends import ai_grok  # noqa: PLC0415

        with self.assertRaises(BackendError) as ctx:
            ai_grok.search("hello")  # 不传 model
        self.assertIn("model", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

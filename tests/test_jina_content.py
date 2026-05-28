"""item1：jina.search(include_content) —— 带正文一次调用，省掉单独抓页。"""

from __future__ import annotations

import os
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "skills" / "search-toolkit" / "scripts"))

from lib import jina  # noqa: E402


class TestJinaIncludeContent(unittest.TestCase):
    def setUp(self):
        os.environ["JINA_API_KEY"] = "test-key"
        self._fake = {
            "data": [
                {"title": "A", "url": "https://a.test", "description": "snip a", "content": "正文A" * 50},
                {"title": "B", "url": "https://b.test", "description": "snip b", "content": "正文B" * 50},
            ]
        }

    def tearDown(self):
        os.environ.pop("JINA_API_KEY", None)

    def _call(self, include_content):
        captured = {}
        def fake_request_json(_method, _url, **kw):
            captured["headers"] = kw.get("headers", {})
            return self._fake
        with mock.patch.object(jina._http, "request_json", side_effect=fake_request_json):
            res = jina.search("q", max_results=5, include_content=include_content)
        return res, captured["headers"]

    def test_default_sends_no_content_header_and_omits_content(self):
        res, headers = self._call(False)
        self.assertEqual(headers.get("X-Respond-With"), "no-content")
        self.assertNotIn("content", res[0])  # 默认不带正文

    def test_with_content_drops_header_and_includes_content(self):
        res, headers = self._call(True)
        self.assertNotIn("X-Respond-With", headers)  # 不再要求 no-content
        self.assertIn("content", res[0])
        self.assertTrue(res[0]["content"].startswith("正文A"))
        self.assertEqual(len(res), 2)


if __name__ == "__main__":
    unittest.main()

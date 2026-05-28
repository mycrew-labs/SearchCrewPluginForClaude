"""bocha 适配器：解析 webPages.value、summary 优先、归一化结构。"""

from __future__ import annotations

import os
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "skills" / "search-toolkit" / "scripts"))

from lib import bocha  # noqa: E402


class TestBocha(unittest.TestCase):
    def setUp(self):
        os.environ["BOCHA_API_KEY"] = "test-key"

    def tearDown(self):
        os.environ.pop("BOCHA_API_KEY", None)

    def test_missing_key_raises(self):
        os.environ.pop("BOCHA_API_KEY", None)
        from lib import BackendError
        with self.assertRaises(BackendError):
            bocha.search("x")

    def test_parses_webpages_and_prefers_summary(self):
        fake = {
            "code": 200, "log_id": "x", "msg": None,
            "data": {
                "webPages": {
                    "value": [
                        {"name": "标题A", "url": "https://a.cn", "snippet": "短", "summary": "较长摘要A",
                         "siteName": "站A", "datePublished": "2026-05-01"},
                        {"name": "标题B", "url": "https://b.cn", "snippet": "只有snippet"},
                    ]
                }
            },
        }
        captured = {}
        def fake_req(_m, _u, **kw):
            captured.update(kw)
            return fake
        with mock.patch.object(bocha._http, "request_json", side_effect=fake_req):
            res = bocha.search("中文查询", max_results=5)
        # 认证 + body
        self.assertEqual(captured["headers"]["Authorization"], "Bearer test-key")
        self.assertTrue(captured["json_body"]["summary"])
        self.assertEqual(captured["json_body"]["query"], "中文查询")
        # 解析：summary 优先，缺则 snippet
        self.assertEqual(res[0]["title"], "标题A")
        self.assertEqual(res[0]["url"], "https://a.cn")
        self.assertEqual(res[0]["snippet"], "较长摘要A")
        self.assertEqual(res[1]["snippet"], "只有snippet")
        self.assertEqual(res[0]["extra"]["source"], "bocha")
        self.assertEqual(res[0]["extra"]["site"], "站A")

    def test_count_clamped_to_50(self):
        captured = {}
        def fake_req(_m, _u, **kw):
            captured.update(kw); return {"webPages": {"value": []}}
        with mock.patch.object(bocha._http, "request_json", side_effect=fake_req):
            bocha.search("x", max_results=200)
        self.assertEqual(captured["json_body"]["count"], 50)


if __name__ == "__main__":
    unittest.main()

"""TC-FETCH: fetch.py 的 raw/HTML 判定、反爬识别、三态分派。"""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "skills" / "search-toolkit" / "scripts"))

import fetch  # noqa: E402


class TestRawDetection(unittest.TestCase):
    def test_text_plain_is_raw(self):
        self.assertTrue(fetch._is_raw_content_type("text/plain", "# hello"))

    def test_json_is_raw(self):
        self.assertTrue(fetch._is_raw_content_type("application/json", '{"a":1}'))

    def test_html_ctype_not_raw(self):
        self.assertFalse(fetch._is_raw_content_type("text/html", "<html>..."))

    def test_empty_ctype_no_html_tags_is_raw(self):
        self.assertTrue(fetch._is_raw_content_type("", "plain text no tags here"))

    def test_empty_ctype_with_html_tags_not_raw(self):
        self.assertFalse(fetch._is_raw_content_type("application/octet-stream", "<!doctype html><html><body>x"))


class TestBlockedDetection(unittest.TestCase):
    def test_short_with_signature_blocked(self):
        self.assertTrue(fetch._looks_blocked("环境异常，完成验证后即可继续访问。去验证"))

    def test_captcha_signature_blocked(self):
        self.assertTrue(fetch._looks_blocked("Warning: requiring CAPTCHA, 拖动下方滑块"))

    def test_long_article_not_blocked(self):
        # 含 captcha 字样但是长正文 → 不误判
        long_text = "本文讲解 captcha 验证码技术的实现。" + ("内容" * 1000)
        self.assertFalse(fetch._looks_blocked(long_text))

    def test_clean_short_not_blocked(self):
        self.assertFalse(fetch._looks_blocked("# 正常标题\n一段正常内容"))


class TestFetchDispatch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["XDG_CONFIG_HOME"] = self.tmp.name
        os.environ["XDG_STATE_HOME"] = self.tmp.name
        os.environ["SEARCH_CREW_RUN_ID"] = "test-fetch"
        from lib import _http
        _http.reset_call_counter()
        self._captured = {}

    def tearDown(self):
        for k in ("XDG_CONFIG_HOME", "XDG_STATE_HOME", "SEARCH_CREW_RUN_ID"):
            os.environ.pop(k, None)
        self.tmp.cleanup()

    def _run(self, url):
        """patch emit 捕获输出 payload。"""
        with mock.patch.object(fetch, "emit", lambda p: self._captured.update(p)):
            with mock.patch.object(sys, "argv", ["fetch.py", url]):
                fetch.main()
        return self._captured

    def test_raw_path(self):
        with mock.patch.object(fetch._http, "request_text_meta", return_value=("# README\n原文内容", "text/plain")):
            out = self._run("https://raw.githubusercontent.com/o/r/main/README.md")
        self.assertEqual(out["source"], "raw")
        self.assertEqual(out["markdown"], "# README\n原文内容")
        self.assertIsNone(out["fallback"])

    def test_html_path(self):
        with mock.patch.object(fetch._http, "request_text_meta", return_value=("<!doctype html><html>...", "text/html")):
            with mock.patch.object(fetch.jina, "fetch", return_value={"url": "u", "markdown": "渲染后 markdown", "source": "jina-reader", "anonymous": False}):
                out = self._run("https://example.com")
        self.assertEqual(out["source"], "jina-reader")
        self.assertEqual(out["markdown"], "渲染后 markdown")

    def test_antibot_on_direct(self):
        with mock.patch.object(fetch._http, "request_text_meta", return_value=("环境异常，完成验证后即可继续访问。去验证", "text/html")):
            out = self._run("https://mp.weixin.qq.com/s?x=1")
        self.assertEqual(out.get("blocked"), "anti_bot")
        self.assertIsNone(out["markdown"])
        self.assertIsNone(out["fallback"])
        self.assertIn(out.get("on_blocked"), ("honest", "collaborate"))  # 策略已透传

    def test_needs_auth_on_403(self):
        from lib import BackendError
        err = BackendError("fetch", "HTTP 403: Forbidden", http_status=403)
        with mock.patch.object(fetch._http, "request_text_meta", side_effect=err):
            out = self._run("https://paper.example.com/paywalled.pdf")
        self.assertEqual(out.get("blocked"), "needs_auth")
        self.assertIsNone(out["fallback"])

    def test_network_fail_still_webfetch_fallback(self):
        from lib import BackendError
        err = BackendError("fetch", "网络错误", retryable=True)  # 非 401/403
        with mock.patch.object(fetch._http, "request_text_meta", side_effect=err):
            out = self._run("https://down.example.com")
        self.assertEqual(out.get("fallback"), "WEBFETCH_FALLBACK")
        self.assertIsNone(out.get("blocked"))

    def test_antibot_after_jina(self):
        # 直连 body 不含签名（长 html），但 Jina 渲染后是验证页
        with mock.patch.object(fetch._http, "request_text_meta", return_value=("<html>" + "x" * 2000 + "</html>", "text/html")):
            with mock.patch.object(fetch.jina, "fetch", return_value={"url": "u", "markdown": "环境异常 去验证", "source": "jina-reader"}):
                out = self._run("https://mp.weixin.qq.com/s?x=2")
        self.assertEqual(out.get("blocked"), "anti_bot")


if __name__ == "__main__":
    unittest.main()

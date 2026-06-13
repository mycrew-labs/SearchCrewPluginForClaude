"""TC-FETCH-ROUTING: 站点 → 抓取能力清单（site-fetch.txt）的解析与 host 匹配。"""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "skills" / "search-toolkit" / "scripts"))

from lib import fetch_routing as fr  # noqa: E402


class TestParseLines(unittest.TestCase):
    def test_basic_two_columns(self):
        m = fr.parse_lines("a.com|real-browser\nb.com|real-browser\n")
        self.assertEqual(m, [("a.com", "real-browser"), ("b.com", "real-browser")])

    def test_capability_optional_defaults_real_browser(self):
        self.assertEqual(fr.parse_lines("foo.com\n"), [("foo.com", "real-browser")])

    def test_comments_and_blank_ignored(self):
        self.assertEqual(
            fr.parse_lines("# 注释\n\n   \nx.com|real-browser\n"),
            [("x.com", "real-browser")],
        )

    def test_host_lowercased(self):
        self.assertEqual(fr.parse_lines("Foo.COM|real-browser\n"), [("foo.com", "real-browser")])


class TestMatching(unittest.TestCase):
    def setUp(self):
        self.m = [("feishu.cn", "real-browser"), ("mp.weixin.qq.com", "real-browser")]

    def test_exact(self):
        self.assertEqual(fr.capability_for_host("feishu.cn", self.m), "real-browser")

    def test_suffix(self):
        self.assertEqual(fr.capability_for_host("x.feishu.cn", self.m), "real-browser")

    def test_no_false_prefix_match(self):
        # notfeishu.cn 不是 .feishu.cn 后缀，不应命中
        self.assertIsNone(fr.capability_for_host("notfeishu.cn", self.m))

    def test_miss(self):
        self.assertIsNone(fr.capability_for_host("example.com", self.m))

    def test_from_url(self):
        self.assertEqual(fr.capability_for_url("https://mp.weixin.qq.com/s/x", self.m), "real-browser")

    def test_unparseable_url(self):
        self.assertIsNone(fr.capability_for_url("not a url", self.m))


class TestLoadMapping(unittest.TestCase):
    def test_default_when_path_none(self):
        m = fr.load_mapping(None)
        self.assertTrue(any(d == "mp.weixin.qq.com" for d, _ in m))

    def test_default_when_file_missing(self):
        m = fr.load_mapping("/no/such/site-fetch-xyz.txt")
        self.assertGreaterEqual(len(m), 6)

    def test_read_explicit_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("# c\nonly.com|real-browser\n")
            path = f.name
        try:
            self.assertEqual(fr.load_mapping(path), [("only.com", "real-browser")])
        finally:
            os.unlink(path)

    def test_empty_file_falls_back_to_default(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("# 全是注释\n\n")
            path = f.name
        try:
            self.assertGreaterEqual(len(fr.load_mapping(path)), 6)
        finally:
            os.unlink(path)

    def test_defaults_site_fetch_txt_parses(self):
        m = fr.load_mapping(REPO_ROOT / "defaults" / "site-fetch.txt")
        self.assertEqual(len(m), 6)
        self.assertTrue(all(cap == "real-browser" for _, cap in m))


if __name__ == "__main__":
    unittest.main()

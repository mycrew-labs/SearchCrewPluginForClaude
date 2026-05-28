"""config-scripted-mutation：changelog / merge --dry-run / promote。

覆盖 active 三个固定写入操作里的 merge（dry-run + 记 log）与 promote（routing /
adapter / 重名 / 坏格式），以及 changelog 追加。
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN_ROOT / "skills" / "search-toolkit" / "scripts"
SEED = SCRIPTS / "seed_user_config.py"
PROMOTE = SCRIPTS / "promote.py"


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.config_root = pathlib.Path(self.tmp.name)
        os.environ["XDG_CONFIG_HOME"] = str(self.config_root)
        os.environ["CLAUDE_PLUGIN_ROOT"] = str(PLUGIN_ROOT)
        self.active = self.config_root / "search-crew"

    def tearDown(self) -> None:
        os.environ.pop("XDG_CONFIG_HOME", None)
        os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
        self.tmp.cleanup()

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, *args],
            capture_output=True,
            text=True,
            env={**os.environ},
        )

    def _seed(self) -> None:
        r = self._run(str(SEED))
        self.assertEqual(r.returncode, 0, r.stderr)

    def _changelog(self) -> str:
        p = self.active / "changelog.log"
        return p.read_text(encoding="utf-8") if p.exists() else ""


class TestChangelogOnSeed(_Base):
    def test_seed_writes_changelog(self) -> None:
        self._seed()
        log = self._changelog()
        self.assertIn("seed", log)
        self.assertIn("trigger=first-install", log)


class TestMergeDryRun(_Base):
    def test_dry_run_reports_missing_without_writing(self) -> None:
        self._seed()
        limits = self.active / "limits.yaml"
        # 删掉一个顶层段模拟 active 落后于 defaults
        text = limits.read_text(encoding="utf-8")
        self.assertIn("call_cap:", text)
        # 截断到 call_cap 之前，制造缺失
        cut = text.split("call_cap:")[0]
        limits.write_text(cut, encoding="utf-8")
        before = limits.read_text(encoding="utf-8")

        r = self._run(str(SEED), "--merge", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("limits.yaml", r.stdout)
        self.assertIn("call_cap", r.stdout)
        # 没写盘
        self.assertEqual(limits.read_text(encoding="utf-8"), before)
        # dry-run 不记 changelog
        self.assertNotIn("merge", self._changelog())

    def test_merge_writes_and_logs(self) -> None:
        self._seed()
        limits = self.active / "limits.yaml"
        text = limits.read_text(encoding="utf-8")
        limits.write_text(text.split("call_cap:")[0], encoding="utf-8")

        r = self._run(str(SEED), "--merge", "--trigger", "setup")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("call_cap:", limits.read_text(encoding="utf-8"))
        log = self._changelog()
        self.assertIn("merge", log)
        self.assertIn("limits.yaml", log)
        self.assertIn("trigger=setup", log)


class TestPromote(_Base):
    def _write_pending(self, kind: str, name: str, content: str) -> pathlib.Path:
        d = self.active / "pending" / kind
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"20260528T140000-{name}.yaml"
        p.write_text(content, encoding="utf-8")
        return p

    def test_promote_routing_appends_topic(self) -> None:
        self._seed()
        pending = self._write_pending(
            "routing",
            "rust-crates",
            "- name: rust-crates\n  description: Rust 包\n  sites:\n    - crates.io\n    - docs.rs\n  hard_rule: false\n",
        )
        r = self._run(str(PROMOTE), str(pending))
        self.assertEqual(r.returncode, 0, r.stderr)
        routing = (self.active / "routing.yaml").read_text(encoding="utf-8")
        self.assertIn("rust-crates", routing)
        self.assertIn("crates.io", routing)
        # 缩进进了 topics（2 空格 + 列表 dash）
        self.assertIn("  - name: rust-crates", routing)
        # pending 已消费
        self.assertFalse(pending.exists())
        # 记 log
        log = self._changelog()
        self.assertIn("promote", log)
        self.assertIn("+topic:rust-crates", log)
        self.assertIn("trigger=user-approved", log)

    def test_promote_routing_still_parses(self) -> None:
        """晋升后 routing.yaml 仍能被项目 YAML 解析器读出新 topic。"""
        self._seed()
        pending = self._write_pending(
            "routing", "mysite", "- name: mysite\n  description: 测试\n  sites:\n    - example.com\n"
        )
        self._run(str(PROMOTE), str(pending))
        proc = self._run(
            "-c",
            "import sys; sys.path.insert(0, r'%s');" % SCRIPTS
            + "from lib import config; r=config.load_routing();"
            + "names=[t['name'] for t in r['topics']]; print('mysite' in names)",
        )
        self.assertEqual(proc.stdout.strip(), "True", proc.stderr)

    def test_promote_routing_bad_format(self) -> None:
        self._seed()
        pending = self._write_pending("routing", "bad", "name: no-dash\ndescription: 缺列表 dash\n")
        r = self._run(str(PROMOTE), str(pending))
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue(pending.exists())  # 失败不消费

    def test_promote_adapter_moves_file(self) -> None:
        self._seed()
        pending = self._write_pending("adapters", "myadapter", "name: myadapter\nkind: yaml\n")
        r = self._run(str(PROMOTE), str(pending))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.active / "adapters" / "myadapter.yaml").exists())
        self.assertFalse(pending.exists())
        self.assertIn("adapters/myadapter.yaml", self._changelog())

    def test_promote_adapter_name_conflict(self) -> None:
        self._seed()
        (self.active / "adapters" / "myadapter.yaml").write_text("existing\n", encoding="utf-8")
        pending = self._write_pending("adapters", "myadapter", "name: myadapter\n")
        r = self._run(str(PROMOTE), str(pending))
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue(pending.exists())  # 没移动
        self.assertEqual(
            (self.active / "adapters" / "myadapter.yaml").read_text(encoding="utf-8"), "existing\n"
        )


if __name__ == "__main__":
    unittest.main()

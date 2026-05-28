"""run_paths.py：subagent 取规范目录，必须与 usage 打点同根。

回归 bug：subagent 自己编 session_id 拼产物目录 → 与 usage.record 写的
run_root(session)/usage.jsonl 分叉 → finalize 读不到 → cost 报 0。
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import unittest

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN_ROOT / "skills" / "search-toolkit" / "scripts"
RUN_PATHS = SCRIPTS / "run_paths.py"


class TestRunPaths(unittest.TestCase):
    def setUp(self) -> None:
        self.env = {**os.environ, "CLAUDE_CODE_SESSION_ID": "unit-test-session"}
        self.env.pop("SEARCH_CREW_RUN_ID", None)
        self.expected_root = pathlib.Path("/tmp/search-crew/unit-test-session")

    def _run(self, *args: str) -> str:
        r = subprocess.run(
            [sys.executable, str(RUN_PATHS), *args],
            capture_output=True, text=True, env=self.env, check=True,
        )
        return r.stdout.strip()

    def test_run_root_uses_session_id(self) -> None:
        self.assertEqual(self._run(), str(self.expected_root))

    def test_subagent_dir_under_run_root(self) -> None:
        out = self._run("--subagent", "fast-search")
        self.assertEqual(out, str(self.expected_root / "fast-search"))
        # 目录被创建
        self.assertTrue(pathlib.Path(out).is_dir())

    def test_aligns_with_usage_record_root(self) -> None:
        """run_paths 的 run_root 必须 == usage 打点用的 runtime.run_root()。"""
        proc = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, r'%s'); from lib import runtime; print(runtime.run_root())" % SCRIPTS],
            capture_output=True, text=True, env=self.env, check=True,
        )
        usage_root = proc.stdout.strip()
        self.assertEqual(self._run(), usage_root)


if __name__ == "__main__":
    unittest.main()

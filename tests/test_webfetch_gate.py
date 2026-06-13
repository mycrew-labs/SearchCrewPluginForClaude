"""TC-WEBFETCH-GATE: PreToolUse hook 分级拦截内置 WebFetch（硬拦 / 软拦 / fail-open / reset）。

hook 是独立脚本、读 stdin JSON，故用 subprocess 喂输入测真实行为。
依赖 fetch_routing 内置默认（微信硬拦、example.com 软拦），不依赖 active 配置存在。
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
GATE = REPO_ROOT / "hooks" / "webfetch_gate.py"
RESET = REPO_ROOT / "hooks" / "session_reset.py"
SID = "unittest-webfetch-gate"
FLAG = pathlib.Path(f"/tmp/.search-crew-webfetch-gate-{SID}")

_ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


def _run(script: pathlib.Path, payload) -> tuple[int, str]:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    p = subprocess.run(
        [sys.executable, str(script)], input=text,
        capture_output=True, text=True, env=_ENV,
    )
    return p.returncode, p.stdout.strip()


def _decision(stdout: str):
    if not stdout:
        return None
    return json.loads(stdout)["hookSpecificOutput"]["permissionDecision"]


class TestWebfetchGate(unittest.TestCase):
    def setUp(self):
        FLAG.unlink(missing_ok=True)

    def tearDown(self):
        FLAG.unlink(missing_ok=True)

    def test_wechat_hard_block_every_time_no_flag(self):
        payload = {"session_id": SID, "tool_input": {"url": "https://mp.weixin.qq.com/s/x"}}
        rc, out = _run(GATE, payload)
        self.assertEqual(rc, 0)
        self.assertEqual(_decision(out), "deny")
        self.assertIn("real-browser", out)
        self.assertFalse(FLAG.exists())  # 硬拦不建 flag
        # 再来一次仍硬拦
        _, out2 = _run(GATE, payload)
        self.assertEqual(_decision(out2), "deny")

    def test_other_domain_soft_block_then_allow(self):
        payload = {"session_id": SID, "tool_input": {"url": "https://example.com/a"}}
        _, out = _run(GATE, payload)
        self.assertEqual(_decision(out), "deny")  # 首次软拦
        self.assertTrue(FLAG.exists())
        _, out2 = _run(GATE, payload)
        self.assertEqual(out2, "")  # retry 放行（无输出）
        self.assertIsNone(_decision(out2))

    def test_fail_open_missing_url(self):
        rc, out = _run(GATE, {"session_id": SID, "tool_input": {}})
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")

    def test_fail_open_bad_json(self):
        rc, out = _run(GATE, "not json at all")
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")

    def test_session_reset_clears_flag(self):
        FLAG.touch()
        _run(RESET, {"session_id": SID})
        self.assertFalse(FLAG.exists())


if __name__ == "__main__":
    unittest.main()

"""ai_summary.py：AI 综述模型配置解析。"""

from __future__ import annotations

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "skills" / "search-toolkit" / "scripts"))

from lib import ai_summary  # noqa: E402


class TestModelConfig(unittest.TestCase):
    def test_object_config_keeps_reasoning_effort(self) -> None:
        cfg = {
            "models": {
                "grok": {
                    "fast": {"model": "grok-4.3", "reasoning_effort": "low"},
                    "deep": {"model": "grok-4.5", "reasoning_effort": "medium"},
                }
            }
        }
        with mock.patch.object(ai_summary, "ai_summary_cfg", return_value=cfg):
            resolved = ai_summary.resolve_model_config("grok", "fast", None)
            self.assertEqual(resolved, {"model": "grok-4.3", "reasoning_effort": "low"})
            self.assertEqual(ai_summary.resolve_model("grok", "deep", None), "grok-4.5")

    def test_string_config_remains_supported(self) -> None:
        cfg = {"models": {"gemini": {"fast": "gemini-2.5-flash-lite"}}}
        with mock.patch.object(ai_summary, "ai_summary_cfg", return_value=cfg):
            self.assertEqual(
                ai_summary.resolve_model_config("gemini", "fast", None),
                {"model": "gemini-2.5-flash-lite"},
            )

    def test_explicit_model_preserves_tier_options(self) -> None:
        cfg = {"models": {"grok": {"fast": {"model": "grok-4.3", "reasoning_effort": "low"}}}}
        with mock.patch.object(ai_summary, "ai_summary_cfg", return_value=cfg):
            self.assertEqual(
                ai_summary.resolve_model_config("grok", "fast", "grok-4.5"),
                {"model": "grok-4.5", "reasoning_effort": "low"},
            )


if __name__ == "__main__":
    unittest.main()

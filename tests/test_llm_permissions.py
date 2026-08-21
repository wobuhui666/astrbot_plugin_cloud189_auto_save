from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import AsyncMock
from pathlib import Path


if "astrbot.api.event" not in sys.modules:
    astrbot = types.ModuleType("astrbot")
    astrbot.__path__ = []
    api = types.ModuleType("astrbot.api")
    api.__path__ = []
    event_module = types.ModuleType("astrbot.api.event")
    event_module.AstrMessageEvent = type("AstrMessageEvent", (), {})
    sys.modules.update(
        {
            "astrbot": astrbot,
            "astrbot.api": api,
            "astrbot.api.event": event_module,
        }
    )

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from astrbot_plugin_cloud189_auto_save.handlers import llm_tools


class FakeEvent:
    def __init__(self, sender_id: str = "user"):
        self.sender_id = sender_id

    def get_sender_id(self):
        return self.sender_id


class FakePlugin:
    def __init__(self, *, allowed: bool = True, admin: bool = False):
        self.allowed = allowed
        self.admin = admin
        self.api = types.SimpleNamespace(
            auto_series=AsyncMock(),
            execute_task=AsyncMock(),
            get_task=AsyncMock(return_value={"id": 1}),
        )

    def is_allowed(self, sender_id: str) -> bool:
        return self.allowed

    def is_admin(self, sender_id: str) -> bool:
        return self.admin


class LlmPermissionTest(unittest.IsolatedAsyncioTestCase):
    async def test_non_admin_cannot_create_auto_series(self):
        plugin = FakePlugin(admin=False)

        result = await llm_tools.create_auto_series(plugin, FakeEvent(), "庆余年")

        self.assertIn("仅管理员", result)
        plugin.api.auto_series.assert_not_awaited()

    async def test_non_admin_cannot_execute_task(self):
        plugin = FakePlugin(admin=False)

        result = await llm_tools.execute_task(plugin, FakeEvent(), 1)

        self.assertIn("仅管理员", result)
        plugin.api.get_task.assert_not_awaited()
        plugin.api.execute_task.assert_not_awaited()

    async def test_non_whitelisted_user_is_rejected_before_admin_check(self):
        plugin = FakePlugin(allowed=False, admin=True)

        result = await llm_tools.execute_task(plugin, FakeEvent(), 1)

        self.assertIn("没有使用", result)
        plugin.api.execute_task.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()

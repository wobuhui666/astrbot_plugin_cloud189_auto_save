"""按 unified_msg_origin / sender 维护的会话状态。

字段对齐 cloud189-auto-save/src/services/telegramBot/session.js,
跨平台共用一份。
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PluginSession:
    key: str = ""
    account_id: int | None = None
    account_entity: dict | None = None
    pending_share: dict[str, Any] = field(default_factory=lambda: {"link": None, "access_code": None})
    search: dict[str, Any] = field(default_factory=lambda: {"active": False, "result_map": {}})
    pt_search: dict[str, Any] = field(
        default_factory=lambda: {"active": False, "preset": None, "results": [], "groups": []}
    )
    folder_nav: dict[str, Any] = field(
        default_factory=lambda: {
            "id": "-11",
            "path": "/",
            "parent_stack": [],
            "folder_cache": {},  # id -> folder dict (from /api/folders/:accountId)
        }
    )
    ui: dict[str, Any] = field(default_factory=dict)
    last_active: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.last_active = time.time()


class SessionStore:
    """简单的内存 SessionStore,定时清理空闲会话。"""

    def __init__(self, idle_seconds: int = 1800, cleanup_interval: int = 600) -> None:
        self._sessions: dict[str, PluginSession] = {}
        self._idle = max(60, int(idle_seconds))
        self._interval = max(30, int(cleanup_interval))
        self._task: asyncio.Task | None = None

    def get(self, key: str) -> PluginSession:
        sess = self._sessions.get(key)
        if sess is None:
            sess = PluginSession(key=key)
            self._sessions[key] = sess
        sess.touch()
        return sess

    def drop(self, key: str) -> None:
        self._sessions.pop(key, None)

    def all(self) -> list[PluginSession]:
        return list(self._sessions.values())

    async def _loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._interval)
                self._sweep()
        except asyncio.CancelledError:
            return

    def _sweep(self) -> None:
        now = time.time()
        expired = [k for k, s in self._sessions.items() if now - s.last_active > self._idle]
        for k in expired:
            self._sessions.pop(k, None)

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # 没有事件循环时先跳过,等首次命令触发再启动
        self._task = loop.create_task(self._loop(), name="cloud189_plugin_session_sweep")

    def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None
        self._sessions.clear()

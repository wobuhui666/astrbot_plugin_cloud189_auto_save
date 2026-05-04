"""所有 handler 共用的工具:权限校验、session_waiter 简化包装、账号选择。"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from astrbot.api.event import AstrMessageEvent

try:  # AstrBot 0.4+
    from astrbot.core.utils.session_waiter import (  # type: ignore
        SessionController,
        session_waiter,
    )
except Exception:  # pragma: no cover
    session_waiter = None  # type: ignore
    SessionController = None  # type: ignore


# ───────────────────── id helpers ─────────────────────

def session_key(event: AstrMessageEvent) -> str:
    """跨平台唯一会话 key。"""
    try:
        return event.unified_msg_origin
    except Exception:
        try:
            return f"{event.get_platform_name()}:{event.get_sender_id()}"
        except Exception:
            return str(getattr(event, "session_id", "anonymous"))


def sender_id(event: AstrMessageEvent) -> str:
    try:
        return str(event.get_sender_id())
    except Exception:
        return ""


# ───────────────────── permission ─────────────────────

def check_allowed(plugin, event) -> str | None:
    if not plugin.is_allowed(sender_id(event)):
        return "🚫 你没有使用本机器人的权限,请联系管理员把你的 ID 加入 allowed_user_ids"
    return None


def check_admin(plugin, event) -> str | None:
    if not plugin.is_admin(sender_id(event)):
        return "⚠️ 仅管理员可执行该操作"
    return None


# ───────────────────── account context ─────────────────────

async def ensure_account(plugin, event) -> tuple[bool, str | None]:
    """确保会话已选中账号。返回 (ok, error_message)。

    优先使用会话内已选中的账号 → 配置里的 default_account_id → 后端第一个账号。
    """
    sess = plugin.sessions.get(session_key(event))
    if sess.account_id:
        return True, None
    default_id = plugin.config.get("default_account_id") or 0
    accounts = await plugin.api.list_accounts()
    if not accounts:
        return False, "❌ 后端未配置任何天翼云盘账号,请先到网页端添加账号"
    pick = None
    if default_id:
        for acc in accounts:
            if int(acc.get("id") or 0) == int(default_id):
                pick = acc
                break
    if not pick:
        pick = accounts[0]
    sess.account_id = int(pick.get("id"))
    sess.account_entity = pick
    return True, None


# ───────────────────── single-message waiter ─────────────────────

async def wait_one(
    event: AstrMessageEvent,
    *,
    timeout: int = 60,
    on_message: Callable[[AstrMessageEvent, "_OneShot"], Awaitable[None]] | None = None,
) -> None:
    """等待用户的下一条消息;on_message 收到后必须自行处理与 stop。

    如果未注册 session_waiter(老版本 AstrBot),则抛出 RuntimeError。
    """
    if session_waiter is None:
        raise RuntimeError(
            "当前 AstrBot 版本未提供 session_waiter,请升级到 v3.4+ 才能使用多轮交互命令"
        )

    one = _OneShot()

    @session_waiter(timeout=timeout, record_history_chains=False)
    async def waiter(controller: "SessionController", ev: AstrMessageEvent):  # type: ignore
        text = (ev.message_str or "").strip()
        if text in {"/cancel", "cancel", "取消"}:
            await ev.send(ev.plain_result("已取消"))
            controller.stop()
            return
        if on_message:
            one.controller = controller
            one.event = ev
            await on_message(ev, one)
        else:
            controller.stop()

    await waiter(event)  # 触发 TimeoutError 由调用方负责捕获


class _OneShot:
    """传给 on_message 的辅助对象,提供 reply / done / keep。"""

    controller: "SessionController" | None = None
    event: AstrMessageEvent | None = None

    async def reply(self, text: str) -> None:
        if self.event is None:
            return
        await self.event.send(self.event.plain_result(text))

    def done(self) -> None:
        if self.controller is not None:
            self.controller.stop()

    def keep(self, *, timeout: int = 60) -> None:
        if self.controller is not None:
            self.controller.keep(timeout=timeout, reset_timeout=True)


# ───────────────────── id parser ─────────────────────

def parse_int_suffix(text: str) -> int | None:
    """从 "/execute_42" 这样的命令尾抽取 42。"""
    if not text:
        return None
    parts = str(text).rsplit("_", 1)
    if len(parts) != 2:
        # 兼容 "/execute 42"
        parts = str(text).rsplit(" ", 1)
        if len(parts) != 2:
            return None
    try:
        return int(parts[-1])
    except ValueError:
        return None


# ───────────────────── pagination helper ─────────────────────

def paginate(items: list, page: int, page_size: int) -> tuple[list, int, int]:
    total = len(items)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size
    return items[start : start + page_size], page, total_pages


# ───────────────────── plain wait (no waiter dep) ─────────────────────

async def short_sleep(seconds: float) -> None:
    await asyncio.sleep(max(0.0, seconds))

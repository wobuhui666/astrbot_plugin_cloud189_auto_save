"""基础命令:/start /help /accounts /cancel /silent。

对齐 cloud189-auto-save/src/services/telegramBot/handlers/basics.js。
"""
from __future__ import annotations

from astrbot.api.event import AstrMessageEvent

from ..api.errors import friendly_error
from ..core.templates import desensitize_username, help_text
from ._common import (
    check_allowed,
    paginate,
    sender_id,
    session_key,
    wait_one,
)


async def handle_start(plugin, event: AstrMessageEvent):
    err = check_allowed(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    sess = plugin.sessions.get(session_key(event))
    cur = (
        f"当前账号:{desensitize_username(sess.account_entity.get('username') if sess.account_entity else None)}"
        if sess.account_id
        else "当前尚未选择账号"
    )
    text = (
        "👋 欢迎使用 cloud189-auto-save 全平台机器人\n"
        "\n"
        f"{cur}\n"
        "\n"
        "推荐你按这个顺序开始:\n"
        "1. /accounts 选择账号\n"
        "2. /fl 查看常用目录\n"
        "3. 直接发送 cloud.189.cn 分享链接创建任务\n"
        "4. /search_cs 搜索 CloudSaver 资源\n"
        "5. /tasks 查看当前任务\n"
        "\n"
        "常用快捷命令:/help /tasks /stats /logs /subs"
    )
    yield event.plain_result(text)


async def handle_help(plugin, event: AstrMessageEvent):
    err = check_allowed(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    yield event.plain_result(help_text())


async def handle_cancel(plugin, event: AstrMessageEvent):
    err = check_allowed(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    sess = plugin.sessions.get(session_key(event))
    sess.search.update({"active": False, "result_map": {}})
    sess.pt_search.update({"active": False, "preset": None, "results": [], "groups": []})
    sess.pending_share = {"link": None, "access_code": None}
    yield event.plain_result("已取消当前操作")


async def handle_silent(plugin, event: AstrMessageEvent, arg: str | None = None):
    err = check_allowed(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    arg = (arg or "").strip().lower()
    cur = bool(plugin.config.get("silent_mode"))
    if arg in ("on", "开"):
        plugin.config["silent_mode"] = True
        plugin.config.save_config()
        yield event.plain_result("🔇 静默模式已开启:之后收到 cloud.189.cn 链接将直接保存到默认目录")
        return
    if arg in ("off", "关"):
        plugin.config["silent_mode"] = False
        plugin.config.save_config()
        yield event.plain_result("🔇 静默模式已关闭:之后收到链接会询问保存目录")
        return
    yield event.plain_result(
        f"🔇 静默模式当前:{'开启' if cur else '关闭'}\n"
        "用法:/silent on  开启;/silent off  关闭。\n"
        "开启后,Bot 处理分享链接时将直接使用默认常用目录创建任务。"
    )


async def handle_accounts(plugin, event: AstrMessageEvent):
    err = check_allowed(plugin, event)
    if err:
        yield event.plain_result(err)
        return

    try:
        accounts = await plugin.api.list_accounts()
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return

    if not accounts:
        yield event.plain_result("📭 后端尚未配置任何账号,请先到网页端添加")
        return

    sess = plugin.sessions.get(session_key(event))
    page_size = int(plugin.config.get("page_size") or 10)
    page_items, page, total_pages = paginate(accounts, 1, max(5, page_size))
    lines = ["👤 账号列表(回复编号选中,/cancel 取消):", ""]
    for idx, acc in enumerate(page_items, 1):
        marker = " ✅" if sess.account_id and int(sess.account_id) == int(acc.get("id") or 0) else ""
        lines.append(
            f"{idx}. #{acc.get('id')} {desensitize_username(acc.get('username'))}{marker}"
        )
    if total_pages > 1:
        lines.append("")
        lines.append(f"(共 {len(accounts)} 个账号,本页 {page}/{total_pages})")
    yield event.plain_result("\n".join(lines))

    async def _on_pick(ev: AstrMessageEvent, ctl):
        text = (ev.message_str or "").strip()
        if not text.isdigit():
            await ctl.reply("⚠️ 请直接回复编号,或回复 /cancel 取消")
            ctl.keep(timeout=60)
            return
        idx = int(text)
        if idx < 1 or idx > len(page_items):
            await ctl.reply("⚠️ 编号超出范围")
            ctl.keep(timeout=60)
            return
        target = page_items[idx - 1]
        sess.account_id = int(target.get("id"))
        sess.account_entity = target
        await ctl.reply(
            f"✅ 已选择账号:{desensitize_username(target.get('username'))}"
        )
        ctl.done()

    try:
        await wait_one(event, timeout=120, on_message=_on_pick)
    except TimeoutError:
        yield event.plain_result("⏰ 选账号超时,已取消")
    except RuntimeError as exc:
        yield event.plain_result(str(exc))

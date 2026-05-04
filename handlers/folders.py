"""目录管理:/fl /fs /df_<id>;以及多轮目录树浏览。

对齐 cloud189-auto-save/src/services/telegramBot/handlers/folders.js。
"""
from __future__ import annotations

import os

from astrbot.api.event import AstrMessageEvent

from ..api.errors import friendly_error
from ..core.templates import common_folder_list, desensitize_username, truncate
from ._common import (
    check_admin,
    check_allowed,
    ensure_account,
    parse_int_suffix,
    session_key,
    wait_one,
)


async def handle_fl(plugin, event: AstrMessageEvent):
    err = check_allowed(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    ok, msg = await ensure_account(plugin, event)
    if not ok:
        yield event.plain_result(msg or "请先 /accounts 选择账号")
        return
    sess = plugin.sessions.get(session_key(event))
    try:
        favorites = await plugin.api.list_favorites(sess.account_id)
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return
    username = sess.account_entity.get("username") if sess.account_entity else None
    yield event.plain_result(common_folder_list(favorites or [], username))


async def handle_fs(plugin, event: AstrMessageEvent):
    err = check_allowed(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    ok, msg = await ensure_account(plugin, event)
    if not ok:
        yield event.plain_result(msg or "请先 /accounts 选择账号")
        return

    sess = plugin.sessions.get(session_key(event))
    nav = sess.folder_nav
    nav["id"] = "-11"
    nav["path"] = "/"
    nav["parent_stack"] = []
    nav["folder_cache"] = {}

    async def _list_and_render(folder_id: str) -> tuple[str, list[dict]]:
        folders = await plugin.api.list_folders(sess.account_id, folder_id=folder_id)
        nav["id"] = folder_id
        for fld in folders:
            nav["folder_cache"][str(fld.get("id"))] = fld
        return _render_folder_view(sess, folders), folders

    try:
        text, folders = await _list_and_render("-11")
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return

    yield event.plain_result(text)

    state = {"current_folders": folders}

    async def _on_msg(ev: AstrMessageEvent, ctl):
        text_in = (ev.message_str or "").strip().lower()
        if text_in in ("/cancel", "cancel", "取消"):
            await ctl.reply("已退出目录浏览")
            ctl.done()
            return
        if text_in in ("save", "ok", "保存", "确认", "确定"):
            current_id = nav["id"]
            current_path = nav["path"] or "/"
            payload = {
                "accountId": sess.account_id,
                "id": current_id,
                "path": current_path.strip("/") or "/",
                "name": (current_path.rstrip("/").split("/")[-1] or "根目录"),
            }
            try:
                await plugin.api.save_favorite(payload)
            except Exception as exc:
                await ctl.reply(friendly_error(exc))
                ctl.done()
                return
            await ctl.reply(f"✅ 已将 {current_path or '/'} 添加为常用目录")
            ctl.done()
            return
        if text_in in ("back", "..", "返回"):
            if not nav["parent_stack"]:
                await ctl.reply("已是根目录,无法继续返回")
                ctl.keep(timeout=120)
                return
            parent_id = nav["parent_stack"].pop() or "-11"
            parts = nav["path"].strip("/").split("/")
            if parts:
                parts.pop()
            nav["path"] = "/" + "/".join(parts) if parts else "/"
            try:
                folders = await plugin.api.list_folders(sess.account_id, folder_id=parent_id)
            except Exception as exc:
                await ctl.reply(friendly_error(exc))
                ctl.done()
                return
            nav["id"] = parent_id
            for fld in folders:
                nav["folder_cache"][str(fld.get("id"))] = fld
            state["current_folders"] = folders
            await ctl.reply(_render_folder_view(sess, folders))
            ctl.keep(timeout=120)
            return
        if not text_in.isdigit():
            await ctl.reply("⚠️ 输入数字进入子目录,或:save 保存 / back 返回 / cancel 退出")
            ctl.keep(timeout=120)
            return
        idx = int(text_in)
        cur = state["current_folders"]
        if idx < 1 or idx > len(cur):
            await ctl.reply("⚠️ 编号超出范围")
            ctl.keep(timeout=120)
            return
        target = cur[idx - 1]
        nav["parent_stack"].append(nav["id"])
        nav["path"] = (nav["path"].rstrip("/") + "/" + target.get("name", "")).replace("//", "/")
        if not nav["path"].startswith("/"):
            nav["path"] = "/" + nav["path"]
        try:
            children = await plugin.api.list_folders(sess.account_id, folder_id=str(target.get("id")))
        except Exception as exc:
            await ctl.reply(friendly_error(exc))
            ctl.done()
            return
        nav["id"] = str(target.get("id"))
        for fld in children:
            nav["folder_cache"][str(fld.get("id"))] = fld
        state["current_folders"] = children
        await ctl.reply(_render_folder_view(sess, children))
        ctl.keep(timeout=120)

    try:
        await wait_one(event, timeout=180, on_message=_on_msg)
    except TimeoutError:
        yield event.plain_result("⏰ 目录浏览超时,已退出")
    except RuntimeError as exc:
        yield event.plain_result(str(exc))


def _render_folder_view(sess, folders: list[dict]) -> str:
    nav = sess.folder_nav
    username = sess.account_entity.get("username") if sess.account_entity else None
    lines = [
        f"📁 目录浏览(账号:{desensitize_username(username)})",
        f"当前路径:{nav.get('path') or '/'}",
        "",
    ]
    if not folders:
        lines.append("📭 当前目录下无子目录")
    else:
        for idx, fld in enumerate(folders, 1):
            lines.append(f"{idx}. {truncate(fld.get('name') or '-', 40)}")
    lines.append("")
    lines.append("操作:数字进入子目录 | save 保存当前目录为常用 | back 返回上级 | cancel 退出")
    return "\n".join(lines)


async def handle_df(plugin, event: AstrMessageEvent, folder_id_text: str):
    err = check_allowed(plugin, event) or check_admin(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    ok, msg = await ensure_account(plugin, event)
    if not ok:
        yield event.plain_result(msg or "请先 /accounts 选择账号")
        return

    folder_id = folder_id_text
    # /df_<id> 中 id 可能是负数
    if "_" in folder_id_text:
        folder_id = folder_id_text.rsplit("_", 1)[-1]

    sess = plugin.sessions.get(session_key(event))
    try:
        favorites = await plugin.api.list_favorites(sess.account_id)
        favorite = next((f for f in favorites or [] if str(f.get("id")) == str(folder_id)), None)
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return

    if not favorite:
        yield event.plain_result("未找到该常用目录(可能已被删除)")
        return

    # 后端没有 DELETE /api/favorites/<id> 端点;改用 saveFavorites 整体覆盖剔除
    new_list = [f for f in favorites if str(f.get("id")) != str(folder_id)]
    try:
        await plugin.api.save_favorite({"accountId": sess.account_id, "favorites": new_list})
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return
    yield event.plain_result(f"✅ 已删除常用目录:{favorite.get('path') or favorite.get('name') or folder_id}")

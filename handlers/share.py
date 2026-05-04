"""分享链接处理:消息中含 cloud.189.cn 时被自动调用。

对齐 cloud189-auto-save/src/services/telegramBot/handlers/share.js。
"""
from __future__ import annotations

from astrbot.api.event import AstrMessageEvent

from ..api.errors import friendly_error
from ..core.share_parser import parse_cloud_share
from ..core.templates import desensitize_username, truncate
from ._common import (
    check_allowed,
    ensure_account,
    session_key,
    wait_one,
)


async def handle_share_link(plugin, event: AstrMessageEvent):
    err = check_allowed(plugin, event)
    if err:
        # 不打扰:无权限就直接静默返回
        return
    text = event.message_str or ""
    url, code = parse_cloud_share(text)
    if not url:
        return

    ok, msg = await ensure_account(plugin, event)
    if not ok:
        yield event.plain_result(msg or "请先 /accounts 选择账号")
        return

    sess = plugin.sessions.get(session_key(event))
    sess.pending_share = {"link": url, "access_code": code}

    # 解析资源名(用 share/parse 接口尝试)
    task_name = ""
    try:
        parsed = await plugin.api.parse_share(sess.account_id, url, code)
        if isinstance(parsed, dict):
            task_name = parsed.get("name") or parsed.get("resourceName") or ""
        elif isinstance(parsed, list) and parsed:
            task_name = parsed[0].get("name") or ""
    except Exception as exc:
        # 解析失败也允许继续创建任务
        yield event.plain_result(friendly_error(exc))
        return

    # 取常用目录
    try:
        favorites = await plugin.api.list_favorites(sess.account_id)
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return

    if not favorites:
        yield event.plain_result(
            "📭 当前账号尚未配置常用目录,请先用 /fs 添加目录后再发送链接。"
        )
        return

    username = desensitize_username(sess.account_entity.get("username") if sess.account_entity else None)
    silent = bool(plugin.config.get("silent_mode"))

    # 静默模式 → 直接用默认目录
    if silent:
        default = next((f for f in favorites if f.get("isDefault")), favorites[0])
        yield event.plain_result(
            f"🔇 静默模式开启,直接保存到默认目录\n"
            f"账号:{username}\n"
            f"资源:{task_name or '(待解析)'}\n"
            f"目录:{default.get('path') or default.get('name')}\n"
            f"⏳ 任务创建中..."
        )
        try:
            await _create_and_execute(plugin, sess, default, url, code)
        except Exception as exc:
            yield event.plain_result(friendly_error(exc))
            return
        yield event.plain_result(f"✅ 任务已创建并提交执行(资源:{task_name or '-'})")
        return

    # 正常模式 → 列出常用目录,等用户编号选择
    lines = [
        f"账号:{username}",
        f"资源:{task_name or '(待解析)'}",
        f"分享链接:{url}",
        "",
        "请选择保存目录(回复编号,/cancel 取消):",
        "",
    ]
    for idx, fld in enumerate(favorites, 1):
        lines.append(f"{idx}. {truncate(fld.get('path') or fld.get('name') or '-', 60)}")
    yield event.plain_result("\n".join(lines))

    async def _on_pick(ev: AstrMessageEvent, ctl):
        text_in = (ev.message_str or "").strip()
        if not text_in.isdigit():
            await ctl.reply("⚠️ 请回复编号,或 /cancel 取消")
            ctl.keep(timeout=90)
            return
        idx = int(text_in)
        if idx < 1 or idx > len(favorites):
            await ctl.reply("⚠️ 编号超出范围")
            ctl.keep(timeout=90)
            return
        target = favorites[idx - 1]
        await ctl.reply(f"⏳ 任务创建中,目标:{target.get('path') or target.get('name')}")
        try:
            await _create_and_execute(plugin, sess, target, url, code)
        except Exception as exc:
            await ctl.reply(friendly_error(exc))
            ctl.done()
            return
        await ctl.reply(f"✅ 任务已创建并执行(资源:{task_name or '-'})")
        ctl.done()

    try:
        await wait_one(event, timeout=120, on_message=_on_pick)
    except TimeoutError:
        yield event.plain_result("⏰ 选目录超时,任务未创建")
    except RuntimeError as exc:
        yield event.plain_result(str(exc))


async def _create_and_execute(plugin, sess, favorite: dict, share_link: str, access_code: str | None):
    payload: dict[str, object] = {
        "accountId": sess.account_id,
        "shareLink": share_link,
        "targetFolderId": favorite.get("id"),
        "targetFolder": favorite.get("path") or favorite.get("name"),
    }
    if access_code:
        payload["accessCode"] = access_code
    payload = {k: v for k, v in payload.items() if v is not None}
    created = await plugin.api.create_task(payload)
    sess.pending_share = {"link": None, "access_code": None}
    # 提交执行
    task_ids: list[int] = []
    if isinstance(created, list):
        task_ids = [int(t.get("id")) for t in created if t and t.get("id")]
    elif isinstance(created, dict) and created.get("id"):
        task_ids = [int(created["id"])]
    for tid in task_ids:
        try:
            await plugin.api.execute_task(tid)
        except Exception:
            pass

"""任务管理:/tasks /tasks_failed/pending/processing /detail_<id>
/execute_<id> /execute_all /strm_<id> /emby_<id> /retry_<id> /dt_<id>。

对齐 cloud189-auto-save/src/services/telegramBot/handlers/tasks.js。
"""
from __future__ import annotations

from astrbot.api.event import AstrMessageEvent

from ..api.errors import friendly_error
from ..core.templates import (
    fmt_status,
    task_card,
    task_detail_card,
    truncate,
)
from ._common import (
    check_admin,
    check_allowed,
    paginate,
    parse_int_suffix,
    session_key,
    wait_one,
)

_STATUS_TITLE = {
    "failed": "失败任务",
    "pending": "待执行任务",
    "processing": "执行中任务",
}


async def _list_tasks_filtered(plugin, status: str | None) -> list[dict]:
    tasks = await plugin.api.list_tasks(status=status)

    def _ts(task: dict) -> str:
        return str(task.get("updatedAt") or task.get("createdAt") or "")

    tasks.sort(key=_ts, reverse=True)
    return tasks


async def _render_page(plugin, event, status: str | None, page: int):
    page_size = int(plugin.config.get("page_size") or 5)
    try:
        tasks = await _list_tasks_filtered(plugin, status)
    except Exception as exc:
        return friendly_error(exc)

    if not tasks:
        if status:
            return f"📭 暂无{_STATUS_TITLE.get(status, '任务')},可使用 /tasks 查看全部任务"
        return "📭 暂无任务,可先发送 cloud.189.cn 分享链接创建任务"

    page_items, page, total_pages = paginate(tasks, page, page_size)
    title = _STATUS_TITLE.get(status or "", "任务列表")
    lines = [f"📋 {title}(第 {page}/{total_pages} 页,共 {len(tasks)} 个):", ""]
    for task in page_items:
        lines.append(task_card(task))
        lines.append("")
    if total_pages > 1:
        cmd = "/tasks"
        if status == "failed":
            cmd = "/tasks_failed"
        elif status == "pending":
            cmd = "/tasks_pending"
        elif status == "processing":
            cmd = "/tasks_processing"
        lines.append(f"翻页:{cmd} <页码>(如 {cmd} {min(page + 1, total_pages)})")
    return "\n".join(lines).rstrip()


async def handle_tasks(plugin, event: AstrMessageEvent, page_arg: str | None = None):
    err = check_allowed(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    page = 1
    if page_arg:
        try:
            page = max(1, int(page_arg))
        except ValueError:
            page = 1
    yield event.plain_result(await _render_page(plugin, event, None, page))


async def handle_tasks_status(plugin, event: AstrMessageEvent, status: str, page_arg: str | None = None):
    err = check_allowed(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    page = 1
    if page_arg:
        try:
            page = max(1, int(page_arg))
        except ValueError:
            page = 1
    yield event.plain_result(await _render_page(plugin, event, status, page))


async def handle_detail(plugin, event: AstrMessageEvent, task_id_text: str):
    err = check_allowed(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    task_id = parse_int_suffix(task_id_text) or _to_int(task_id_text)
    if task_id is None:
        yield event.plain_result("⚠️ 任务ID无效")
        return
    try:
        task = await plugin.api.get_task(task_id)
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return
    if not task:
        yield event.plain_result("未找到该任务")
        return
    yield event.plain_result(task_detail_card(task))


async def handle_execute(plugin, event: AstrMessageEvent, task_id_text: str):
    err = check_allowed(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    task_id = parse_int_suffix(task_id_text) or _to_int(task_id_text)
    if task_id is None:
        yield event.plain_result("⚠️ 任务ID无效")
        return
    yield event.plain_result(f"⏳ 任务 #{task_id} 开始执行...")
    try:
        await plugin.api.execute_task(task_id)
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return
    yield event.plain_result(f"✅ 任务 #{task_id} 执行完成")


async def handle_execute_all(plugin, event: AstrMessageEvent):
    err = check_allowed(plugin, event) or check_admin(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    yield event.plain_result("⏳ 开始执行所有任务...")
    try:
        await plugin.api.execute_all()
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return
    yield event.plain_result("✅ 所有任务执行完成")


async def handle_strm(plugin, event: AstrMessageEvent, task_id_text: str):
    err = check_allowed(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    task_id = parse_int_suffix(task_id_text) or _to_int(task_id_text)
    if task_id is None:
        yield event.plain_result("⚠️ 任务ID无效")
        return
    yield event.plain_result(f"⏳ 开始为任务 #{task_id} 生成 STRM...")
    try:
        await plugin.api.make_strm([task_id])
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return
    yield event.plain_result(f"✅ 任务 #{task_id} STRM 生成请求已提交")


async def handle_emby(plugin, event: AstrMessageEvent, task_id_text: str):
    err = check_allowed(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    task_id = parse_int_suffix(task_id_text) or _to_int(task_id_text)
    if task_id is None:
        yield event.plain_result("⚠️ 任务ID无效")
        return
    # 后端没有专用 Emby 通知端点;Emby 通知通常在 /api/tasks/:id/execute 之后由后端流程触发,
    # 这里复用 execute 触发刮削/通知链路。
    yield event.plain_result(f"⏳ 触发 Emby 通知(执行任务 #{task_id})...")
    try:
        await plugin.api.execute_task(task_id)
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return
    yield event.plain_result(f"✅ 任务 #{task_id} 已重新执行,Emby 将由后端流水线刮削")


async def handle_retry(plugin, event: AstrMessageEvent, task_id_text: str):
    err = check_allowed(plugin, event) or check_admin(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    task_id = parse_int_suffix(task_id_text) or _to_int(task_id_text)
    if task_id is None:
        yield event.plain_result("⚠️ 任务ID无效")
        return
    try:
        task = await plugin.api.get_task(task_id)
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return
    if not task:
        yield event.plain_result("未找到该任务")
        return
    if (task.get("status") or "").lower() != "failed":
        yield event.plain_result(
            f"⚠️ 该任务状态为 {fmt_status(task.get('status'))},仅失败任务可重试"
        )
        return
    yield event.plain_result(f"🔄 重置任务 #{task_id} 并开始执行...")
    try:
        await plugin.api.update_task(task_id, {"status": "pending", "lastError": None})
        await plugin.api.execute_task(task_id)
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return
    yield event.plain_result(f"✅ 任务 #{task_id} 重试执行完成")


async def handle_delete(plugin, event: AstrMessageEvent, task_id_text: str):
    err = check_allowed(plugin, event) or check_admin(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    task_id = parse_int_suffix(task_id_text) or _to_int(task_id_text)
    if task_id is None:
        yield event.plain_result("⚠️ 任务ID无效")
        return

    yield event.plain_result(
        f"🗑 即将删除任务 #{task_id}\n"
        "请回复:\n"
        "  y      → 仅删除任务(保留网盘文件)\n"
        "  yc     → 同时删除网盘文件\n"
        "  n / cancel → 取消"
    )

    state = {"resolved": False}

    async def _on_choice(ev: AstrMessageEvent, ctl):
        if state["resolved"]:
            return
        text = (ev.message_str or "").strip().lower()
        if text in ("n", "no", "否", "/cancel", "cancel", "取消"):
            await ctl.reply("已取消删除")
            state["resolved"] = True
            ctl.done()
            return
        delete_cloud = text in ("yc", "yes-cloud", "同步删除", "同步")
        if text not in ("y", "yes", "是", "yc", "yes-cloud", "同步删除", "同步"):
            await ctl.reply("⚠️ 无效输入,请回复 y / yc / n")
            ctl.keep(timeout=60)
            return
        try:
            await plugin.api.delete_task(task_id, delete_cloud=delete_cloud)
        except Exception as exc:
            await ctl.reply(friendly_error(exc))
            state["resolved"] = True
            ctl.done()
            return
        suffix = "(已同步删除网盘文件)" if delete_cloud else ""
        await ctl.reply(f"✅ 任务 #{task_id} 已删除{suffix}")
        state["resolved"] = True
        ctl.done()

    try:
        await wait_one(event, timeout=60, on_message=_on_choice)
    except TimeoutError:
        yield event.plain_result("⏰ 删除确认超时,已取消")
    except RuntimeError as exc:
        yield event.plain_result(str(exc))


def _to_int(text: str | None) -> int | None:
    if text is None:
        return None
    text = str(text).strip()
    if not text or not text.lstrip("-").isdigit():
        return None
    try:
        return int(text)
    except ValueError:
        return None

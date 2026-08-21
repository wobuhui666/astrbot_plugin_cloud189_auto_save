"""主项目统一审计历史的查询命令。"""
from __future__ import annotations

from astrbot.api.event import AstrMessageEvent

from ..api.errors import friendly_error
from ..core.templates import audit_detail_card, audit_runs_card
from ._common import check_allowed


async def handle_history(
    plugin,
    event: AstrMessageEvent,
    keyword: str = "",
    page_text: str = "",
):
    err = check_allowed(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    try:
        page = max(1, int(page_text or 1))
    except ValueError:
        page = 1
    try:
        data = await plugin.api.audit_runs(
            page=page,
            page_size=int(plugin.config.get("page_size") or 5),
            keyword=(keyword or "").strip() or None,
        )
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return
    yield event.plain_result(audit_runs_card(data))


async def handle_history_detail(plugin, event: AstrMessageEvent, run_id: str):
    err = check_allowed(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    run_id = (run_id or "").strip()
    if not run_id:
        yield event.plain_result("用法:/history_detail RUN_ID")
        return
    try:
        data = await plugin.api.audit_run_detail(run_id)
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return
    yield event.plain_result(audit_detail_card(data))

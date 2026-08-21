"""影巢搜索、天翼资源查询与签到。"""
from __future__ import annotations

from astrbot.api.event import AstrMessageEvent

from ..api.errors import friendly_error
from ..core.templates import hdhive_resources_card, hdhive_search_card
from ._common import check_allowed


async def handle_hdhive(plugin, event: AstrMessageEvent, keyword: str):
    err = check_allowed(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    keyword = (keyword or "").strip()
    if not keyword:
        yield event.plain_result("用法:/hdhive 关键词")
        return
    try:
        result = await plugin.api.hdhive_search(keyword, limit=12)
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return
    yield event.plain_result(hdhive_search_card(result))


async def handle_hdhive_resources(
    plugin,
    event: AstrMessageEvent,
    media_type: str,
    tmdb_id: str,
):
    err = check_allowed(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    media_type = (media_type or "").strip().lower()
    tmdb_id = (tmdb_id or "").strip()
    if media_type not in {"movie", "tv"} or not tmdb_id:
        yield event.plain_result("用法:/hdhive_resources movie|tv TMDB_ID")
        return
    try:
        resources = await plugin.api.hdhive_resources(media_type, tmdb_id)
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return
    yield event.plain_result(hdhive_resources_card(resources, media_type, tmdb_id))


async def handle_hdhive_checkin(plugin, event: AstrMessageEvent):
    err = check_allowed(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    try:
        status = await plugin.api.hdhive_status()
        if not status.get("enabled"):
            yield event.plain_result("未启用影巢，请先在网页端媒体设置中启用并配置授权")
            return
        result = await plugin.api.hdhive_checkin()
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return
    message = result.get("message") if isinstance(result, dict) else ""
    yield event.plain_result(f"✅ {message or '影巢签到成功'}")

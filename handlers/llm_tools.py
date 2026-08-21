"""AstrBot LLM Tool 的非交互实现。"""
from __future__ import annotations

import asyncio

from ..api.errors import friendly_error
from ..core.templates import (
    audit_detail_card,
    audit_runs_card,
    auto_series_intents_card,
    hdhive_search_card,
    pt_status_card,
    task_card,
    task_detail_card,
    truncate,
)
from ._common import check_admin, check_allowed


def _permission_error(plugin, event, *, admin: bool = False) -> str | None:
    return check_allowed(plugin, event) or (check_admin(plugin, event) if admin else None)


async def query_tasks(
    plugin,
    event,
    status: str = "",
    keyword: str = "",
    task_id: int = 0,
    limit: int = 10,
) -> str:
    if err := _permission_error(plugin, event):
        return err
    try:
        if int(task_id or 0) > 0:
            task = await plugin.api.get_task(int(task_id))
            if not task:
                return f"未找到任务 #{task_id}"
            safe_task = dict(task)
            safe_task["shareLink"] = "[已隐藏]"
            safe_task.pop("accessCode", None)
            return task_detail_card(safe_task)
        normalized_status = (status or "").strip().lower()
        if normalized_status and normalized_status not in {
            "pending",
            "processing",
            "completed",
            "failed",
        }:
            return "status 仅支持 pending、processing、completed、failed 或空字符串"
        size = max(1, min(int(limit or 10), 30))
        tasks = await plugin.api.list_tasks(
            status=normalized_status or None,
            keyword=(keyword or "").strip() or None,
            limit=size,
        )
    except Exception as exc:
        return friendly_error(exc)
    if not tasks:
        return "没有匹配的任务"
    lines = [f"匹配到 {len(tasks)} 个任务:"]
    for task in tasks[:size]:
        lines.extend(["", task_card(task)])
    return "\n".join(lines)


async def system_status(plugin, event) -> str:
    if err := _permission_error(plugin, event):
        return err
    try:
        tasks, pt_payload, version = await asyncio.gather(
            plugin.api.list_tasks(),
            plugin.api.pt_releases_all(limit=500),
            plugin.api.version(),
        )
    except Exception as exc:
        return friendly_error(exc)
    counts: dict[str, int] = {}
    for task in tasks:
        status = str(task.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    version_text = version.get("version") if isinstance(version, dict) else version
    task_text = (
        f"后端版本:{version_text or '-'}\n"
        f"任务总数:{len(tasks)} 待执行:{counts.get('pending', 0)} "
        f"执行中:{counts.get('processing', 0)} 失败:{counts.get('failed', 0)}\n\n"
    )
    return task_text + pt_status_card(pt_payload, limit=8)


async def search_media(plugin, event, keyword: str, source: str = "all") -> str:
    if err := _permission_error(plugin, event):
        return err
    keyword = (keyword or "").strip()
    source = (source or "all").strip().lower()
    if not keyword:
        return "keyword 不能为空"
    if source not in {"all", "cloudsaver", "hdhive", "tmdb"}:
        return "source 仅支持 all、cloudsaver、hdhive、tmdb"

    names = [source] if source != "all" else ["cloudsaver", "hdhive", "tmdb"]
    calls = {
        "cloudsaver": lambda: plugin.api.cloudsaver_search(keyword),
        "hdhive": lambda: plugin.api.hdhive_search(keyword, limit=8),
        "tmdb": lambda: plugin.api.tmdb_search(keyword),
    }
    results = await asyncio.gather(*(calls[name]() for name in names), return_exceptions=True)
    sections: list[str] = []
    for name, result in zip(names, results):
        if isinstance(result, Exception):
            sections.append(f"{name}: {friendly_error(result)}")
            continue
        if name == "cloudsaver":
            lines = ["CloudSaver:"]
            for item in (result or [])[:8]:
                link = ""
                if item.get("cloudLinks"):
                    link = item["cloudLinks"][0].get("link") or ""
                lines.append(f"• {truncate(item.get('title') or item.get('name') or '-', 56)}")
                if link:
                    lines.append(f"  {link}")
            if len(lines) == 1:
                lines.append("未找到结果")
            sections.append("\n".join(lines))
        elif name == "hdhive":
            sections.append(hdhive_search_card(result or {}))
        else:
            movies = (result or {}).get("movies") or []
            shows = (result or {}).get("tvShows") or []
            lines = ["TMDB:"]
            for item in [*movies[:4], *shows[:4]]:
                date = item.get("releaseDate") or "-"
                lines.append(f"• {truncate(item.get('title') or '-', 48)} ({date})")
            if len(lines) == 1:
                lines.append("未找到结果")
            sections.append("\n".join(lines))
    return "\n\n".join(sections)


async def list_auto_series(plugin, event, limit: int = 10) -> str:
    if err := _permission_error(plugin, event):
        return err
    try:
        intents = await plugin.api.auto_series_intents()
    except Exception as exc:
        return friendly_error(exc)
    return auto_series_intents_card(intents, limit=max(1, min(int(limit or 10), 30)))


async def create_auto_series(
    plugin,
    event,
    title: str,
    year: str = "",
    mode: str = "",
) -> str:
    if err := _permission_error(plugin, event, admin=True):
        return err
    title = (title or "").strip()
    mode = (mode or "").strip().lower()
    if not title:
        return "title 不能为空"
    if mode and mode not in {"normal", "lazy"}:
        return "mode 仅支持 normal、lazy 或空字符串"
    try:
        if not mode:
            settings = await plugin.api.auto_series_settings()
            mode = str(settings.get("mode") or "normal")
        result = await plugin.api.auto_series(
            title=title,
            year=(year or "").strip() or None,
            mode=mode,
        )
    except Exception as exc:
        return friendly_error(exc)
    return (
        f"已创建自动追剧 Intent: {title}\n"
        f"Intent ID:{result.get('intentId') or '-'}\n"
        f"状态:{result.get('status') or 'pending'}\n"
        f"模式:{mode}"
    )


async def control_auto_series(plugin, event, intent_id: str, action: str) -> str:
    if err := _permission_error(plugin, event, admin=True):
        return err
    intent_id = (intent_id or "").strip()
    action = (action or "").strip().lower()
    if not intent_id:
        return "intent_id 不能为空"
    if action not in {"pause", "resume", "run"}:
        return "action 仅支持 pause、resume、run"
    try:
        result = await plugin.api.auto_series_intent_action(intent_id, action)
    except Exception as exc:
        return friendly_error(exc)
    status = result.get("status") if isinstance(result, dict) else ""
    return f"自动追剧 {intent_id} 已执行 {action}" + (f"，当前状态:{status}" if status else "")


async def query_history(
    plugin,
    event,
    keyword: str = "",
    module: str = "",
    status: str = "",
    run_id: str = "",
    limit: int = 10,
) -> str:
    if err := _permission_error(plugin, event):
        return err
    try:
        if (run_id or "").strip():
            detail = await plugin.api.audit_run_detail(run_id.strip())
            return audit_detail_card(detail)
        data = await plugin.api.audit_runs(
            page=1,
            page_size=max(1, min(int(limit or 10), 50)),
            keyword=(keyword or "").strip() or None,
            module=(module or "").strip() or None,
            status=(status or "").strip() or None,
        )
    except Exception as exc:
        return friendly_error(exc)
    return audit_runs_card(data)


async def execute_task(plugin, event, task_id: int) -> str:
    if err := _permission_error(plugin, event, admin=True):
        return err
    try:
        task_id = int(task_id)
        if task_id <= 0:
            return "task_id 必须是正整数"
        task = await plugin.api.get_task(task_id)
        if not task:
            return f"未找到任务 #{task_id}"
        await plugin.api.execute_task(task_id)
    except Exception as exc:
        return friendly_error(exc)
    return f"任务 #{task_id} 已提交执行"


async def hdhive_checkin(plugin, event) -> str:
    if err := _permission_error(plugin, event, admin=True):
        return err
    try:
        result = await plugin.api.hdhive_checkin()
    except Exception as exc:
        return friendly_error(exc)
    message = result.get("message") if isinstance(result, dict) else ""
    return message or "影巢签到成功"

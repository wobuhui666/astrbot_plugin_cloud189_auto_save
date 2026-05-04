"""统计、日志、订阅 handler。

对齐 telegramBot/handlers/stats.js / logs.js / subs.js。
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

from astrbot.api.event import AstrMessageEvent

from ..api.errors import friendly_error
from ..core.templates import fmt_time, stats_card
from ..core.templates import truncate as _truncate
from ._common import check_allowed, paginate, parse_int_suffix


# ───────────────────── /stats ─────────────────────

async def handle_stats(plugin, event: AstrMessageEvent):
    err = check_allowed(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    try:
        all_tasks = await plugin.api.list_tasks()
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return

    status_counts: dict[str, int] = {}
    for task in all_tasks:
        s = (task.get("status") or "unknown").lower()
        status_counts[s] = status_counts.get(s, 0) + 1

    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent = 0
    failed_top: list[dict] = []
    for task in all_tasks:
        created = task.get("createdAt")
        try:
            if created and isinstance(created, str):
                ts = created.replace("Z", "+00:00")
                if datetime.fromisoformat(ts).replace(tzinfo=None) >= seven_days_ago:
                    recent += 1
        except Exception:
            pass
        if (task.get("status") or "").lower() == "failed":
            failed_top.append(task)

    failed_top.sort(key=lambda t: str(t.get("updatedAt") or ""), reverse=True)
    yield event.plain_result(stats_card(status_counts, recent, failed_top[:5]))


# ───────────────────── /logs ─────────────────────

async def handle_logs(plugin, event: AstrMessageEvent, task_id_text: str | None = None):
    err = check_allowed(plugin, event)
    if err:
        yield event.plain_result(err)
        return

    log_path = (plugin.config.get("log_file_path") or "").strip()
    if not log_path:
        yield event.plain_result(
            "ℹ️ /logs 未启用。\n"
            "若插件与 cloud189-auto-save 后端在同一台机器,请在插件配置里把 log_file_path 设置为后端日志路径(默认 /tmp/cloud189-app.log)。"
        )
        return
    if not os.path.exists(log_path):
        yield event.plain_result(f"📭 日志文件不存在:{log_path}")
        return

    max_lines = int(plugin.config.get("log_max_lines") or 30)
    task_id = parse_int_suffix(task_id_text or "") if task_id_text else None

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as fp:
            content = fp.read()
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return

    lines = [line for line in content.splitlines() if line.strip()]
    if task_id is not None:
        keywords = [f"id:{task_id}"]
        try:
            task = await plugin.api.get_task(task_id)
            if task and task.get("resourceName"):
                keywords.append(task["resourceName"])
        except Exception:
            pass
        lines = [line for line in lines if any(k in line for k in keywords if k)]
        if not lines:
            yield event.plain_result(f"📭 未找到任务 #{task_id} 相关日志")
            return

    tail = lines[-max_lines:]
    header = (
        f"📋 任务 #{task_id} 日志(最近 {len(tail)} 条)"
        if task_id is not None
        else f"📋 系统日志(最近 {len(tail)} 条)"
    )
    body = "\n".join(_truncate(l, 200) for l in tail)
    yield event.plain_result(f"{header}\n\n{body}")


# ───────────────────── /subs ─────────────────────

async def handle_subs(plugin, event: AstrMessageEvent, page_arg: str | None = None):
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

    try:
        subs = await plugin.api.list_subscriptions()
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return

    if not subs:
        yield event.plain_result("📭 暂无订阅")
        return

    page_size = int(plugin.config.get("page_size") or 5)
    page_items, page, total_pages = paginate(subs, page, page_size)
    lines = [f"📡 订阅列表(第 {page}/{total_pages} 页,共 {len(subs)} 个):", ""]
    for sub in page_items:
        status = "✅ 启用" if sub.get("enabled") else "❌ 禁用"
        refresh_status = sub.get("lastRefreshStatus") or "unknown"
        refresh_time = fmt_time(sub.get("lastRefreshTime"))
        lines.append(
            f"#{sub.get('id')} {sub.get('name') or '-'}  {status}\n"
            f"  UUID:{sub.get('uuid') or '-'}\n"
            f"  刷新:{refresh_status} @ {refresh_time}\n"
            f"  有效/失效资源:{sub.get('validResourceCount') or 0}/{sub.get('invalidResourceCount') or 0}\n"
            f"  操作:/subs_refresh_{sub.get('id')}"
        )
        lines.append("")
    if total_pages > 1:
        lines.append(f"翻页:/subs {min(page + 1, total_pages)}")
    yield event.plain_result("\n".join(lines).rstrip())


async def handle_subs_refresh(plugin, event: AstrMessageEvent, sub_id_text: str):
    err = check_allowed(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    sub_id = parse_int_suffix(sub_id_text)
    if sub_id is None:
        yield event.plain_result("⚠️ 订阅 ID 无效")
        return
    yield event.plain_result(f"🔄 正在刷新订阅 #{sub_id}...")
    try:
        await plugin.api.refresh_subscription(sub_id)
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return
    yield event.plain_result(f"✅ 订阅 #{sub_id} 刷新完成")

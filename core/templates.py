"""文本模板,移植自 cloud189-auto-save/src/services/telegramBot/templates.js。

为保证全平台兼容(QQ/微信不支持 Telegram 的 HTML 标签),
所有输出统一使用纯文本。
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any


# ───────────────────── helpers ─────────────────────

def desensitize_username(username: str | None) -> str:
    if not username:
        return "未知账号"
    name = str(username)
    # 邮箱:保留首字母与 @ 之后部分
    if "@" in name:
        local, domain = name.split("@", 1)
        if len(local) <= 1:
            return f"{local}***@{domain}"
        return f"{local[0]}***@{domain}"
    # 手机号:中间 4 位脱敏
    if re.fullmatch(r"\d{11}", name):
        return f"{name[:3]}****{name[-4:]}"
    if len(name) <= 2:
        return name[0] + "*"
    return f"{name[0]}***{name[-1]}"


def fmt_status(status: str | None) -> str:
    s = (status or "").lower()
    return {
        "pending": "⏳ 待执行",
        "processing": "🔄 执行中",
        "completed": "✅ 已完成",
        "failed": "❌ 失败",
    }.get(s, status or "未知")


def fmt_time(value: Any) -> str:
    if not value:
        return "-"
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(int(value) / 1000 if value > 1e12 else int(value)).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        text = str(value)
        # ISO 字符串
        text = text.replace("Z", "+00:00")
        return datetime.fromisoformat(text).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(value)


def truncate(text: str | None, limit: int = 60) -> str:
    if not text:
        return ""
    s = str(text)
    if len(s) <= limit:
        return s
    return s[: limit - 1] + "…"


def fmt_speed(value: Any) -> str:
    """把后端返回的 bytes/s 转成便于阅读的速率。"""
    try:
        speed = max(0.0, float(value or 0))
    except (TypeError, ValueError):
        speed = 0.0
    units = ("B/s", "KB/s", "MB/s", "GB/s", "TB/s")
    unit_index = 0
    while speed >= 1024 and unit_index < len(units) - 1:
        speed /= 1024
        unit_index += 1
    return f"{speed:.1f} {units[unit_index]}"


# ───────────────────── cards ─────────────────────

def task_card(task: dict) -> str:
    """对应 templates.js 的 taskCard(),纯文本版。"""
    name = task.get("resourceName") or task.get("shareFolderName") or "未命名任务"
    if task.get("shareFolderName") and task.get("resourceName"):
        name = f"{task['resourceName']}/{task['shareFolderName']}"
    lines = [
        f"#{task.get('id')} {fmt_status(task.get('status'))}  {truncate(name, 60)}",
        f"  📂 目标:{truncate(task.get('targetFolder') or task.get('realFolder') or '-', 60)}",
        f"  🕐 更新:{fmt_time(task.get('updatedAt') or task.get('createdAt'))}",
    ]
    if task.get("lastError"):
        lines.append(f"  ⚠️ {truncate(task['lastError'], 80)}")
    lines.append(f"  操作:/detail_{task.get('id')}  /execute_{task.get('id')}")
    return "\n".join(lines)


def task_detail_card(task: dict) -> str:
    """对应 templates.js 的 taskDetailCard()。"""
    name = task.get("resourceName") or task.get("shareFolderName") or "未命名"
    lines = [
        f"📄 任务详情 #{task.get('id')}",
        "",
        f"📛 名称:{name}",
        f"🔘 状态:{fmt_status(task.get('status'))}",
        f"📂 保存目录:{task.get('targetFolder') or task.get('realFolder') or '-'}",
        f"🔗 分享链接:{task.get('shareLink') or '-'}",
    ]
    if task.get("accessCode"):
        lines.append(f"🔑 访问码:{task['accessCode']}")
    if task.get("matchPattern"):
        lines.append(f"✅ 匹配规则:{task['matchPattern']}")
    if task.get("excludePattern"):
        lines.append(f"❌ 排除规则:{task['excludePattern']}")
    if task.get("cron"):
        lines.append(f"⏰ Cron:{task['cron']}")
    lines.extend(
        [
            f"🕐 创建:{fmt_time(task.get('createdAt'))}",
            f"🕐 更新:{fmt_time(task.get('updatedAt'))}",
        ]
    )
    if task.get("lastError"):
        lines.append("")
        lines.append(f"⚠️ 错误:{task['lastError']}")
    lines.extend(
        [
            "",
            f"操作:/execute_{task.get('id')}  /strm_{task.get('id')}  /emby_{task.get('id')}",
            f"     /retry_{task.get('id')}(管理员)  /dt_{task.get('id')}(管理员)",
        ]
    )
    return "\n".join(lines)


def stats_card(status_counts: dict[str, int], recent_count: int, failed_top: list[dict]) -> str:
    total = sum(status_counts.values())
    lines = [
        "📊 系统统计",
        "",
        f"📦 任务总数:{total}",
        f"⏳ 待执行:{status_counts.get('pending', 0)}",
        f"🔄 执行中:{status_counts.get('processing', 0)}",
        f"✅ 已完成:{status_counts.get('completed', 0)}",
        f"❌ 失败:{status_counts.get('failed', 0)}",
        f"📅 近 7 天新增:{recent_count}",
    ]
    if failed_top:
        lines.extend(["", "🔝 最近失败 TOP5"])
        for task in failed_top[:5]:
            name = task.get("resourceName") or task.get("shareFolderName") or "-"
            lines.append(f"  • #{task.get('id')} {truncate(name, 40)} → /detail_{task.get('id')}")
    return "\n".join(lines)


def common_folder_list(folders: list[dict], username: str | None) -> str:
    lines = [f"📁 常用目录(账号:{desensitize_username(username)})"]
    if not folders:
        lines.append("")
        lines.append("📭 暂无常用目录,请用 /fs 添加")
        return "\n".join(lines)
    lines.append("")
    for idx, folder in enumerate(folders, 1):
        path = folder.get("path") or folder.get("name") or "-"
        lines.append(f"{idx}. {path}")
        lines.append(f"   删除:/df_{folder.get('id')}")
    return "\n".join(lines)


def search_results(results: list[dict]) -> str:
    """对应 templates.js 的 searchResults(),编号化呈现。"""
    lines: list[str] = []
    for idx, item in enumerate(results, 1):
        title = item.get("title") or item.get("name") or "-"
        lines.append(f"{idx}. {truncate(title, 60)}")
        link = ""
        if item.get("cloudLinks"):
            link = item["cloudLinks"][0].get("link") or ""
        if link:
            lines.append(f"   {link}")
    if not lines:
        return "未找到相关资源"
    lines.append("")
    lines.append("回复编号即可转存对应资源,/cancel 退出搜索模式")
    return "\n".join(lines)


def pt_sub_card(sub: dict, idx: int | None = None) -> str:
    enabled = "✅ 启用" if sub.get("enabled") else "❌ 禁用"
    head = f"#{sub.get('id')}" if idx is None else f"{idx}. #{sub.get('id')}"
    lines = [
        f"{head} {sub.get('name') or '-'}  {enabled}",
        f"   📡 源:{sub.get('sourcePreset') or '-'}",
        f"   📂 目标:{sub.get('targetFolder') or sub.get('targetFolderId') or '-'}",
        f"   🔗 RSS:{truncate(sub.get('rssUrl') or '-', 80)}",
        f"   📦 Release 数:{sub.get('releaseCount') or 0}",
        f"   操作:/pt_detail_{sub.get('id')}  /pt_releases_{sub.get('id')}  /pt_refresh_{sub.get('id')}(管理员)  /pt_toggle_{sub.get('id')}(管理员)",
    ]
    return "\n".join(lines)


def pt_release_card(release: dict, idx: int | None = None) -> str:
    head = f"#{release.get('id')}" if idx is None else f"{idx}. #{release.get('id')}"
    return (
        f"{head} {truncate(release.get('title') or release.get('name') or '-', 60)}\n"
        f"   状态:{release.get('status') or '-'}  发布:{fmt_time(release.get('publishDate'))}\n"
        f"   保存:{truncate(release.get('savedPath') or '-', 60)}"
    )


def pt_status_card(payload: dict, *, limit: int = 10) -> str:
    releases = payload.get("releases") or []
    transfer = payload.get("transferStats") or {}
    counts: dict[str, int] = {}
    for release in releases:
        status = str(release.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1

    active_statuses = {"pending", "downloading", "downloaded", "uploading"}
    active = [item for item in releases if item.get("status") in active_statuses]
    lines = [
        "📡 PT 全局状态",
        "",
        f"⬇️ PT 总下载速度:{fmt_speed(transfer.get('downloadSpeed'))}",
        f"⬆️ 天翼总上传速度:{fmt_speed(transfer.get('cloudUploadSpeed'))}",
        f"📦 Release 总数:{len(releases)}  进行中:{len(active)}  失败:{counts.get('failed', 0) + counts.get('upload_failed', 0)}",
    ]
    if not active:
        lines.extend(["", "当前没有进行中的 PT 任务"])
        return "\n".join(lines)

    lines.extend(["", "进行中的任务"])
    for release in active[: max(1, limit)]:
        downloader = release.get("downloader") or {}
        progress = downloader.get("progress")
        progress_text = f" {progress}%" if progress is not None else ""
        lines.append(
            f"#{release.get('id')} [{release.get('status') or '-'}{progress_text}] "
            f"{truncate(release.get('title') or release.get('name') or '-', 48)}"
        )
        if release.get("status") == "downloading":
            lines.append(f"   下载:{fmt_speed(downloader.get('downloadSpeed'))}")
    return "\n".join(lines)


def hdhive_search_card(result: dict) -> str:
    items = result.get("items") or []
    if not items:
        warning = result.get("warning") or "未找到影巢资源"
        return str(warning)
    lines = ["🎞 影巢搜索结果", ""]
    for idx, item in enumerate(items, 1):
        media_type = item.get("type") or "unknown"
        tmdb_id = item.get("tmdbId") or item.get("id") or "-"
        year = f" ({item.get('year')})" if item.get("year") else ""
        lines.append(f"{idx}. {truncate(item.get('title') or '-', 52)}{year}")
        if item.get("shareLink"):
            lines.append(f"   天翼链接:{item.get('shareLink')}")
        elif media_type in {"movie", "tv"} and tmdb_id != "-":
            lines.append(f"   查天翼:/hdhive_resources {media_type} {tmdb_id}")
    if result.get("warning"):
        lines.extend(["", f"提示:{truncate(result.get('warning'), 160)}"])
    return "\n".join(lines)


def hdhive_resources_card(resources: list[dict], media_type: str, tmdb_id: str) -> str:
    if not resources:
        return "未找到可用的影巢天翼资源"
    lines = [f"🎞 影巢天翼资源({media_type}/{tmdb_id})", ""]
    for idx, item in enumerate(resources, 1):
        points = item.get("points")
        cost = "免费" if item.get("isFree") else (f"{points} 积分" if points is not None else "积分未知")
        state = "已解锁" if item.get("link") or item.get("isUnlocked") else cost
        lines.append(f"{idx}. {truncate(item.get('title') or '-', 52)} [{state}]")
        if item.get("sizeFormatted"):
            lines.append(f"   大小:{item.get('sizeFormatted')}")
        if item.get("link"):
            code = f" 访问码:{item.get('code')}" if item.get("code") else ""
            lines.append(f"   {item.get('link')}{code}")
    if any(not item.get("link") for item in resources):
        lines.extend(["", "未解锁资源请在网页端确认积分后解锁，插件不会自动消费积分。"])
    return "\n".join(lines)


def auto_series_intents_card(intents: list[dict], *, limit: int = 10) -> str:
    if not intents:
        return "📭 暂无自动追剧 Intent"
    lines = [f"📺 自动追剧 Intent(共 {len(intents)} 个)", ""]
    for intent in intents[: max(1, limit)]:
        agent = "Agent" if intent.get("agentEnabled") else "确定性"
        lines.append(
            f"• {truncate(intent.get('title') or '-', 36)} [{intent.get('status') or '-'} / {agent}]"
        )
        lines.append(f"  ID:{intent.get('id')}")
        if intent.get("lastError"):
            lines.append(f"  错误:{truncate(intent.get('lastError'), 100)}")
    return "\n".join(lines)


def audit_runs_card(data: dict) -> str:
    items = data.get("items") or []
    stats = data.get("stats") or {}
    if not items:
        return "📭 没有匹配的历史记录"
    page = data.get("page") or 1
    pages = data.get("pages") or 1
    lines = [
        f"🕘 历史记录(第 {page}/{pages} 页,共 {data.get('total') or len(items)} 条)",
        f"变更:{stats.get('changes', 0)} 失败:{stats.get('failures', 0)} 运行中:{stats.get('running', 0)}",
        "",
    ]
    for item in items:
        subject = item.get("subjectName") or item.get("subjectId") or "-"
        lines.append(
            f"• [{item.get('status') or '-'}] {item.get('module') or '-'} / {truncate(subject, 36)}"
        )
        lines.append(f"  {fmt_time(item.get('startedAt'))}  变更:{item.get('changeCount') or 0} 失败:{item.get('failureCount') or 0}")
        if item.get("summary"):
            lines.append(f"  {truncate(item.get('summary'), 80)}")
        lines.append(f"  详情:/history_detail {item.get('id')}")
    return "\n".join(lines)


def audit_detail_card(data: dict) -> str:
    run = data.get("run") or {}
    events = data.get("events") or []
    operations = data.get("operations") or []
    lines = [
        "🕘 历史详情",
        "",
        f"ID:{run.get('id') or '-'}",
        f"模块:{run.get('module') or '-'}  状态:{run.get('status') or '-'}",
        f"对象:{run.get('subjectName') or run.get('subjectId') or '-'}",
        f"开始:{fmt_time(run.get('startedAt'))}",
        f"摘要:{truncate(run.get('summary') or '-', 180)}",
        f"操作:{len(operations)}  事件:{len(events)}  失败:{run.get('failureCount') or 0}",
    ]
    if operations:
        lines.extend(["", "最近操作"])
        for operation in operations[-5:]:
            path = operation.get("targetPath") or operation.get("sourcePath") or ""
            lines.append(
                f"• [{operation.get('status') or '-'}] {operation.get('action') or '-'} "
                f"{truncate(path, 56)}"
            )
            if operation.get("error"):
                lines.append(f"  {truncate(operation.get('error'), 100)}")
    if events:
        lines.extend(["", "最近事件"])
        for event in events[-5:]:
            lines.append(
                f"• [{event.get('level') or 'info'}] {truncate(event.get('message') or event.get('type') or '-', 90)}"
            )
    return "\n".join(lines)


def help_text() -> str:
    return (
        "📖 cloud189-auto-save 全平台机器人帮助\n"
        "\n"
        "🧱 基础\n"
        "  /start            首次使用引导\n"
        "  /help             显示本帮助\n"
        "  /accounts         切换天翼账号\n"
        "  /silent [on|off]  静默模式开关\n"
        "  /cancel           取消当前操作\n"
        "\n"
        "📋 任务管理\n"
        "  /tasks [page]     任务列表分页\n"
        "  /tasks_failed     失败任务\n"
        "  /tasks_pending    待执行任务\n"
        "  /tasks_processing 执行中任务\n"
        "  /detail_<id>      任务详情\n"
        "  /execute_<id>     执行单任务\n"
        "  /execute_all      执行所有任务(管理员)\n"
        "  /strm_<id>        生成 STRM\n"
        "  /emby_<id>        通知 Emby\n"
        "  /retry_<id>       重试失败任务(管理员)\n"
        "  /dt_<id>          删除任务(管理员)\n"
        "\n"
        "📁 目录\n"
        "  /fl               常用目录列表\n"
        "  /fs               添加常用目录(目录树浏览)\n"
        "  /df_<id>          删除常用目录(管理员)\n"
        "\n"
        "🔍 搜索 / 追剧\n"
        "  /search_cs        进入 CloudSaver 搜索模式\n"
        "  /hdhive 关键词     搜索影巢资源\n"
        "  /hdhive_resources movie|tv ID  查询影巢天翼资源\n"
        "  /hdhive_checkin    执行影巢签到\n"
        "  /tmdb 标题 [年]    TMDB 影视搜索\n"
        "  /series 标题 [年]  自动追剧(正常任务)\n"
        "  /lazy_series 标题  自动追剧(懒转存 STRM)\n"
        "  /series_intents    自动追剧 Intent 列表\n"
        "  /series_pause ID   暂停追剧(管理员)\n"
        "  /series_resume ID  恢复追剧(管理员)\n"
        "  /series_run ID     立即运行追剧(管理员)\n"
        "\n"
        "📊 统计 / 日志 / 订阅\n"
        "  /stats            系统统计\n"
        "  /logs [task_id]   查看日志(限同机部署)\n"
        "  /subs             订阅列表\n"
        "  /history [关键词]  统一审计历史\n"
        "  /history_detail ID 历史操作详情\n"
        "\n"
        "📡 PT\n"
        "  /pt_search                进入 PT 搜索模式\n"
        "  /pt_status                全局任务与总传输速度\n"
        "  /pt_subs                  PT 订阅列表\n"
        "  /pt_detail_<id>           PT 订阅详情\n"
        "  /pt_releases_<id>         查看订阅 Release\n"
        "  /pt_refresh_<id>          手动刷新(管理员)\n"
        "  /pt_toggle_<id>           启用/禁用(管理员)\n"
        "  /pt_retry_<id>            Release 重试(管理员)\n"
        "  /pt_del_<id>              Release 删除(管理员)\n"
        "\n"
        "💡 提示:直接发送 cloud.189.cn 分享链接即可创建转存任务；也可在自然语言对话中让 LLM 查询和执行已授权操作。"
    )

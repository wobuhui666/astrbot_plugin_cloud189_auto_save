"""搜索:/search_cs(CloudSaver) /tmdb 与 /series /lazy_series。

对齐 telegramBot/handlers/search.js 与 series.js。
"""
from __future__ import annotations

import re

from astrbot.api.event import AstrMessageEvent

from ..api.errors import friendly_error
from ..core.share_parser import parse_cloud_share
from ..core.templates import auto_series_intents_card, search_results, truncate
from ._common import (
    check_admin,
    check_allowed,
    ensure_account,
    session_key,
    wait_one,
)


# ───────────────────── /search_cs ─────────────────────

async def handle_search_cs(plugin, event: AstrMessageEvent):
    err = check_allowed(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    ok, msg = await ensure_account(plugin, event)
    if not ok:
        yield event.plain_result(msg or "请先 /accounts 选择账号")
        return

    sess = plugin.sessions.get(session_key(event))
    sess.search.update({"active": True, "result_map": {}})

    timeout = int(plugin.config.get("search_timeout_seconds") or 180)

    yield event.plain_result(
        "🔍 已进入 CloudSaver 搜索模式\n"
        "• 输入关键词搜索资源\n"
        "• 输入编号转存对应资源\n"
        "• 直接发送 cloud.189.cn 链接也会被识别\n"
        f"• {timeout} 秒未操作将自动退出 / 输入 /cancel 退出"
    )

    async def _on_msg(ev: AstrMessageEvent, ctl):
        text_in = (ev.message_str or "").strip()
        if not text_in:
            ctl.keep(timeout=timeout)
            return
        if text_in.lower() in ("/cancel", "cancel", "退出", "取消"):
            sess.search.update({"active": False, "result_map": {}})
            await ctl.reply("已退出搜索模式")
            ctl.done()
            return

        # 1) cloud.189.cn 链接优先
        url, code = parse_cloud_share(text_in)
        if url:
            sess.search.update({"active": False, "result_map": {}})
            sess.pending_share = {"link": url, "access_code": code}
            await ctl.reply("检测到分享链接,已退出搜索模式;请直接重发链接由分享流程处理。")
            ctl.done()
            return

        # 2) 数字 → 编号选择
        if text_in.isdigit():
            idx = int(text_in)
            link = sess.search["result_map"].get(idx)
            if not link:
                await ctl.reply("⚠️ 无效的编号")
                ctl.keep(timeout=timeout)
                return
            url2, code2 = parse_cloud_share(link)
            if not url2:
                await ctl.reply("⚠️ 该资源不是 cloud.189.cn 分享链接")
                ctl.keep(timeout=timeout)
                return
            sess.search.update({"active": False, "result_map": {}})
            sess.pending_share = {"link": url2, "access_code": code2}
            await ctl.reply(f"已选择编号 {idx},请直接重发链接由分享流程处理 → {url2}")
            ctl.done()
            return

        # 3) 关键词搜索
        await ctl.reply("🔍 搜索中...")
        try:
            results = await plugin.api.cloudsaver_search(text_in)
        except Exception as exc:
            await ctl.reply(friendly_error(exc))
            ctl.keep(timeout=timeout)
            return
        if not results:
            await ctl.reply("未找到相关资源")
            ctl.keep(timeout=timeout)
            return
        sess.search["result_map"] = {}
        for i, item in enumerate(results, 1):
            link = ""
            if item.get("cloudLinks"):
                link = item["cloudLinks"][0].get("link") or ""
            if link:
                sess.search["result_map"][i] = link
        await ctl.reply(search_results(results))
        ctl.keep(timeout=timeout)

    try:
        await wait_one(event, timeout=timeout, on_message=_on_msg)
    except TimeoutError:
        sess.search.update({"active": False, "result_map": {}})
        yield event.plain_result("⏰ 长时间未搜索,已自动退出 CloudSaver 搜索模式")
    except RuntimeError as exc:
        sess.search.update({"active": False, "result_map": {}})
        yield event.plain_result(str(exc))


# ───────────────────── /tmdb ─────────────────────

_YEAR_RE = re.compile(r"^(.+?)(?:\s+(\d{4}))?\s*$")


def _parse_title_year(text: str) -> tuple[str, str | None]:
    m = _YEAR_RE.match((text or "").strip())
    if not m:
        return (text or "").strip(), None
    return m.group(1).strip(), (m.group(2) or None)


async def handle_tmdb(plugin, event: AstrMessageEvent, query: str | None):
    err = check_allowed(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    if not query:
        yield event.plain_result("用法:/tmdb 标题 [年]")
        return
    title, year = _parse_title_year(query)
    yield event.plain_result(f"🔍 正在搜索 TMDB:{title}{(' ' + year) if year else ''}")
    try:
        result = await plugin.api.tmdb_search(title, year)
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return

    movies = (result or {}).get("movies") or []
    tvs = (result or {}).get("tvShows") or []
    if not movies and not tvs:
        yield event.plain_result("未找到相关影视信息")
        return

    lines: list[str] = []
    if movies:
        lines.append("📽 电影")
        for m in movies[:5]:
            overview = truncate(m.get("overview") or "暂无", 40)
            lines.append(
                f"  • {m.get('title')}({m.get('originalTitle') or '-'})\n"
                f"    上映:{m.get('releaseDate') or '-'}  评分:{m.get('voteAverage') or '-'}\n"
                f"    简介:{overview}"
            )
    if tvs:
        if lines:
            lines.append("")
        lines.append("📺 剧集")
        for t in tvs[:5]:
            overview = truncate(t.get("overview") or "暂无", 40)
            lines.append(
                f"  • {t.get('title')}({t.get('originalTitle') or '-'})\n"
                f"    首播:{t.get('releaseDate') or '-'}  评分:{t.get('voteAverage') or '-'}\n"
                f"    简介:{overview}"
            )
    yield event.plain_result("\n".join(lines))


# ───────────────────── /series & /lazy_series ─────────────────────

async def handle_series(plugin, event: AstrMessageEvent, raw: str | None, mode: str = "normal"):
    err = check_allowed(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    if not raw:
        cmd = "/lazy_series" if mode == "lazy" else "/series"
        yield event.plain_result(f"请输入剧名,格式:{cmd} 剧名 [年份]")
        return
    title, year = _parse_title_year(raw)
    label = "懒转存STRM" if mode == "lazy" else "正常任务"
    yield event.plain_result(f"⏳ 自动追剧({label}):{title}{(' ' + year) if year else ''}")
    try:
        result = await plugin.api.auto_series(title=title, year=year, mode=mode)
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return
    if result.get("intentId"):
        yield event.plain_result(
            "✅ 已创建自动追剧 Intent\n"
            f"剧名:{title}\n"
            f"模式:{'懒转存STRM' if mode == 'lazy' else '自动转存'}\n"
            f"状态:{result.get('status') or 'pending'}\n"
            f"Intent ID:{result.get('intentId')}\n"
            f"Workflow ID:{result.get('workflowRunId') or '-'}"
        )
    elif mode == "lazy":
        yield event.plain_result(
            "✅ 懒转存STRM 已生成\n"
            f"剧名:{result.get('taskName') or title}\n"
            f"资源:{result.get('resourceTitle') or '-'}\n"
            f"文件数:{result.get('fileCount') or 0}"
        )
    else:
        yield event.plain_result(
            "✅ 自动追剧已完成\n"
            f"剧名:{result.get('taskName') or title}\n"
            f"资源:{result.get('resourceTitle') or '-'}\n"
            f"任务数:{result.get('taskCount') or 0}"
        )


async def handle_series_intents(plugin, event: AstrMessageEvent):
    err = check_allowed(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    try:
        intents = await plugin.api.auto_series_intents()
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return
    yield event.plain_result(
        auto_series_intents_card(intents, limit=max(5, int(plugin.config.get("page_size") or 5)))
    )


async def handle_series_action(
    plugin,
    event: AstrMessageEvent,
    intent_id: str,
    action: str,
):
    err = check_allowed(plugin, event) or check_admin(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    intent_id = (intent_id or "").strip()
    if not intent_id or action not in {"pause", "resume", "run"}:
        yield event.plain_result("用法:/series_pause|series_resume|series_run INTENT_ID")
        return
    try:
        result = await plugin.api.auto_series_intent_action(intent_id, action)
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return
    labels = {"pause": "已暂停", "resume": "已恢复", "run": "已提交立即运行"}
    status = result.get("status") if isinstance(result, dict) else ""
    yield event.plain_result(f"✅ 自动追剧 {intent_id} {labels[action]}{f',状态:{status}' if status else ''}")

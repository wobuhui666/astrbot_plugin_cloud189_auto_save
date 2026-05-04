"""PT 站点搜索与订阅管理。

对齐 telegramBot/handlers/ptSearch.js 与 ptSubs.js。
"""
from __future__ import annotations

from astrbot.api.event import AstrMessageEvent

from ..api.errors import friendly_error
from ..core.templates import fmt_time, pt_release_card, pt_sub_card, truncate
from ._common import (
    check_admin,
    check_allowed,
    paginate,
    parse_int_suffix,
    session_key,
    wait_one,
)

# fallback 站点(后端 /api/pt/sources/presets 不可用时使用)
_FALLBACK_PRESETS = [
    {"key": "anibt", "label": "AniBT"},
    {"key": "mikan", "label": "蜜柑"},
    {"key": "animegarden", "label": "AnimeGarden"},
    {"key": "nyaa", "label": "Nyaa"},
    {"key": "dmhy", "label": "动漫花园"},
]


# ───────────────────── /pt_search ─────────────────────

async def handle_pt_search(plugin, event: AstrMessageEvent):
    err = check_allowed(plugin, event)
    if err:
        yield event.plain_result(err)
        return

    sess = plugin.sessions.get(session_key(event))
    sess.pt_search.update({"active": True, "preset": None, "results": [], "groups": []})

    try:
        presets = await plugin.api.pt_presets()
    except Exception:
        presets = []
    if not presets:
        presets = _FALLBACK_PRESETS

    lines = ["🔍 PT 搜索 — 选择站点(回复编号):", ""]
    for idx, preset in enumerate(presets, 1):
        key = preset.get("key") or preset
        label = preset.get("label") or key
        lines.append(f"{idx}. {label}({key})")
    lines.append("")
    lines.append("/cancel 退出")

    yield event.plain_result("\n".join(lines))

    timeout = int(plugin.config.get("search_timeout_seconds") or 180)

    async def _on_msg(ev: AstrMessageEvent, ctl):
        text_in = (ev.message_str or "").strip()
        if text_in.lower() in ("/cancel", "cancel", "退出", "取消"):
            sess.pt_search.update({"active": False, "preset": None, "results": [], "groups": []})
            await ctl.reply("已退出 PT 搜索")
            ctl.done()
            return

        # ── 站点未选 → 等待编号选站点 ──
        if not sess.pt_search.get("preset"):
            if not text_in.isdigit():
                await ctl.reply("⚠️ 请回复站点编号")
                ctl.keep(timeout=timeout)
                return
            idx = int(text_in)
            if idx < 1 or idx > len(presets):
                await ctl.reply("⚠️ 编号超出范围")
                ctl.keep(timeout=timeout)
                return
            chosen = presets[idx - 1]
            preset_key = chosen.get("key") or chosen
            label = chosen.get("label") or preset_key
            sess.pt_search["preset"] = preset_key
            await ctl.reply(
                f"已选择 {label},请输入搜索关键词 / 输入编号选择字幕组(出结果后)"
            )
            ctl.keep(timeout=timeout)
            return

        # ── 数字 → 编号选择(结果或字幕组) ──
        if text_in.isdigit():
            idx = int(text_in)
            results = sess.pt_search.get("results") or []
            groups = sess.pt_search.get("groups") or []
            if results and 1 <= idx <= len(results):
                selected = results[idx - 1]
                if selected.get("directRss"):
                    await _show_rss(ctl, selected)
                    sess.pt_search["active"] = False
                    ctl.done()
                    return
                # 取字幕组
                preset = sess.pt_search.get("preset")
                try:
                    grps = await plugin.api.pt_groups(preset, bgm_id=selected.get("id"))
                except Exception as exc:
                    await ctl.reply(friendly_error(exc))
                    ctl.keep(timeout=timeout)
                    return
                if not grps:
                    await ctl.reply("未找到字幕组")
                    ctl.keep(timeout=timeout)
                    return
                if len(grps) == 1:
                    await _show_rss(ctl, grps[0])
                    sess.pt_search["active"] = False
                    ctl.done()
                    return
                sess.pt_search["groups"] = grps
                lines2 = [f"选择字幕组(回复编号):", ""]
                for i, g in enumerate(grps, 1):
                    extra = f"({g.get('itemCount')} 资源)" if g.get("itemCount") else ""
                    lines2.append(f"{i}. {g.get('name') or g.get('group') or '-'} {extra}")
                await ctl.reply("\n".join(lines2))
                ctl.keep(timeout=timeout)
                return
            if groups and 1 <= idx <= len(groups):
                await _show_rss(ctl, groups[idx - 1])
                sess.pt_search["active"] = False
                ctl.done()
                return
            await ctl.reply("⚠️ 无效编号")
            ctl.keep(timeout=timeout)
            return

        # ── 关键词搜索 ──
        preset = sess.pt_search.get("preset")
        await ctl.reply("🔍 正在搜索...")
        try:
            results = await plugin.api.pt_search(preset, text_in)
        except Exception as exc:
            await ctl.reply(friendly_error(exc))
            ctl.keep(timeout=timeout)
            return
        if not results:
            await ctl.reply("未找到相关资源")
            ctl.keep(timeout=timeout)
            return
        sess.pt_search["results"] = results
        sess.pt_search["groups"] = []

        if results[0].get("directRss"):
            r = results[0]
            text_lines = [f"搜索结果:{r.get('title') or '-'}"]
            if r.get("preview"):
                text_lines.append("最新资源预览:")
                for t in r["preview"]:
                    text_lines.append(f"  • {t}")
            if r.get("groups"):
                sess.pt_search["groups"] = r["groups"]
                text_lines.append("")
                text_lines.append("可用字幕组(回复编号):")
                for i, g in enumerate(r["groups"], 1):
                    text_lines.append(
                        f"{i}. {g.get('name') or '-'} ({g.get('itemCount') or 0} 资源)"
                    )
            else:
                text_lines.append("")
                text_lines.append(f"RSS:{r.get('url') or '-'}")
                sess.pt_search["active"] = False
            await ctl.reply("\n".join(text_lines))
            if not sess.pt_search["active"]:
                ctl.done()
                return
            ctl.keep(timeout=timeout)
            return

        # 标准模式
        text_lines = ["搜索结果:", ""]
        for i, r in enumerate(results, 1):
            text_lines.append(f"{i}. {truncate(r.get('title') or '-', 60)}")
        text_lines.append("")
        text_lines.append("回复编号选择番剧 / 直接换关键词重搜")
        await ctl.reply("\n".join(text_lines))
        ctl.keep(timeout=timeout)

    try:
        await wait_one(event, timeout=timeout, on_message=_on_msg)
    except TimeoutError:
        sess.pt_search.update({"active": False, "preset": None, "results": [], "groups": []})
        yield event.plain_result("⏰ 长时间未操作,已自动退出 PT 搜索模式")
    except RuntimeError as exc:
        sess.pt_search.update({"active": False, "preset": None, "results": [], "groups": []})
        yield event.plain_result(str(exc))


async def _show_rss(ctl, group: dict):
    name = group.get("name") or group.get("group") or "-"
    source = group.get("source") or group.get("preset") or "-"
    rss = group.get("rssUrl") or group.get("url") or "-"
    await ctl.reply(
        "✅ RSS 地址:\n"
        f"站点:{source}\n"
        f"字幕组:{name}\n"
        f"{rss}\n\n"
        "可在 PT 订阅中使用此 RSS 地址"
    )


# ───────────────────── /pt_subs ─────────────────────

async def handle_pt_subs(plugin, event: AstrMessageEvent, page_arg: str | None = None):
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
        subs = await plugin.api.pt_subs_list()
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return
    if not subs:
        yield event.plain_result("📭 暂无 PT 订阅")
        return
    page_size = int(plugin.config.get("page_size") or 5)
    items, page, total_pages = paginate(subs, page, page_size)
    lines = [f"📡 PT 订阅列表(第 {page}/{total_pages} 页,共 {len(subs)} 个):", ""]
    for idx, sub in enumerate(items, (page - 1) * page_size + 1):
        lines.append(pt_sub_card(sub, idx))
        lines.append("")
    if total_pages > 1:
        lines.append(f"翻页:/pt_subs {min(page + 1, total_pages)}")
    yield event.plain_result("\n".join(lines).rstrip())


async def handle_pt_detail(plugin, event: AstrMessageEvent, sub_id_text: str):
    err = check_allowed(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    sub_id = parse_int_suffix(sub_id_text)
    if sub_id is None:
        yield event.plain_result("⚠️ 订阅 ID 无效")
        return
    try:
        subs = await plugin.api.pt_subs_list()
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return
    sub = next((s for s in subs if int(s.get("id") or 0) == int(sub_id)), None)
    if not sub:
        yield event.plain_result("⚠️ 订阅不存在")
        return
    try:
        page = await plugin.api.pt_sub_releases(sub_id, page=1, page_size=5)
    except Exception:
        page = {"releases": [], "total": 0}
    releases = page.get("releases") if isinstance(page, dict) else (page or [])

    enabled = "✅ 启用" if sub.get("enabled") else "❌ 禁用"
    last_check = fmt_time(sub.get("lastCheckTime"))
    last_status = sub.get("lastStatus")
    last_status_label = (
        "✅ 正常" if last_status == "ok" else ("❌ 异常" if last_status == "error" else "未知")
    )
    lines = [
        "📡 PT 订阅详情",
        "",
        f"🆔 ID:{sub.get('id')}",
        f"📛 名称:{sub.get('name') or '-'}",
        f"📡 来源:{sub.get('sourcePreset') or '-'}",
        f"🔗 RSS:{sub.get('rssUrl') or '-'}",
        f"📂 目标:{sub.get('targetFolder') or sub.get('targetFolderId') or '-'}",
        f"🔘 状态:{enabled}",
        f"🕐 最后检查:{last_check}",
        f"📊 检查结果:{last_status_label}",
        f"💬 最后消息:{truncate(sub.get('lastMessage') or '-', 200)}",
        f"📦 Release 数:{sub.get('releaseCount') or 0}",
    ]
    if sub.get("includePattern"):
        lines.append(f"✅ 包含正则:{sub['includePattern']}")
    if sub.get("excludePattern"):
        lines.append(f"❌ 排除正则:{sub['excludePattern']}")
    if releases:
        lines.append("")
        lines.append("📋 最近 Release")
        for i, rel in enumerate(releases, 1):
            lines.append(pt_release_card(rel, i))
    lines.extend(
        [
            "",
            f"操作:/pt_releases_{sub.get('id')}  /pt_refresh_{sub.get('id')}(管理员)  /pt_toggle_{sub.get('id')}(管理员)",
        ]
    )
    yield event.plain_result("\n".join(lines))


async def handle_pt_refresh(plugin, event: AstrMessageEvent, sub_id_text: str):
    err = check_allowed(plugin, event) or check_admin(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    sub_id = parse_int_suffix(sub_id_text)
    if sub_id is None:
        yield event.plain_result("⚠️ 订阅 ID 无效")
        return
    yield event.plain_result(f"🔄 正在刷新 PT 订阅 #{sub_id}...")
    try:
        result = await plugin.api.pt_sub_refresh(sub_id)
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return
    count = 0
    if isinstance(result, dict):
        count = int(result.get("processed") or 0)
    yield event.plain_result(f"✅ 刷新完成,本次新增 {count} 条 release")


async def handle_pt_toggle(plugin, event: AstrMessageEvent, sub_id_text: str):
    err = check_allowed(plugin, event) or check_admin(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    sub_id = parse_int_suffix(sub_id_text)
    if sub_id is None:
        yield event.plain_result("⚠️ 订阅 ID 无效")
        return
    try:
        subs = await plugin.api.pt_subs_list()
        sub = next((s for s in subs if int(s.get("id") or 0) == int(sub_id)), None)
        if not sub:
            yield event.plain_result("⚠️ 订阅不存在")
            return
        new_enabled = not bool(sub.get("enabled"))
        await plugin.api.pt_sub_update(sub_id, {"enabled": new_enabled})
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return
    yield event.plain_result(f"{'✅ 已启用' if new_enabled else '❌ 已禁用'}:{sub.get('name') or sub_id}")


async def handle_pt_releases(plugin, event: AstrMessageEvent, sub_id_text: str, page_arg: str | None = None):
    err = check_allowed(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    sub_id = parse_int_suffix(sub_id_text)
    if sub_id is None:
        yield event.plain_result("⚠️ 订阅 ID 无效")
        return
    page = 1
    if page_arg:
        try:
            page = max(1, int(page_arg))
        except ValueError:
            page = 1
    page_size = int(plugin.config.get("page_size") or 5)
    try:
        page_data = await plugin.api.pt_sub_releases(sub_id, page=page, page_size=page_size)
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return
    releases = page_data.get("releases") if isinstance(page_data, dict) else (page_data or [])
    total = page_data.get("total") if isinstance(page_data, dict) else len(releases)
    if not releases:
        yield event.plain_result("📭 暂无 release")
        return
    total_pages = max(1, (int(total) + page_size - 1) // page_size)
    lines = [f"📋 订阅 #{sub_id} Releases(第 {page}/{total_pages} 页,共 {total} 个):", ""]
    for idx, rel in enumerate(releases, (page - 1) * page_size + 1):
        lines.append(pt_release_card(rel, idx))
        if rel.get("status") in ("failed", "upload_failed"):
            lines.append(f"   🔁 重试:/pt_retry_{rel.get('id')}  🗑 删除:/pt_del_{rel.get('id')}")
        lines.append("")
    if total_pages > 1:
        lines.append(f"翻页:/pt_releases_{sub_id} {min(page + 1, total_pages)}")
    yield event.plain_result("\n".join(lines).rstrip())


async def handle_pt_retry(plugin, event: AstrMessageEvent, release_id_text: str):
    err = check_allowed(plugin, event) or check_admin(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    rid = parse_int_suffix(release_id_text)
    if rid is None:
        yield event.plain_result("⚠️ Release ID 无效")
        return
    try:
        await plugin.api.pt_release_retry(rid)
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return
    yield event.plain_result(f"✅ Release {rid} 已重试")


async def handle_pt_del(plugin, event: AstrMessageEvent, release_id_text: str):
    err = check_allowed(plugin, event) or check_admin(plugin, event)
    if err:
        yield event.plain_result(err)
        return
    rid = parse_int_suffix(release_id_text)
    if rid is None:
        yield event.plain_result("⚠️ Release ID 无效")
        return
    try:
        await plugin.api.pt_release_delete(rid, delete_files=True)
    except Exception as exc:
        yield event.plain_result(friendly_error(exc))
        return
    yield event.plain_result(f"🗑 Release {rid} 已删除")

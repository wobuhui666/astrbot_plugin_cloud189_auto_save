"""AstrBot 插件入口:把所有命令注册到 Star 子类上,委托到 handlers/。

完整复刻 cloud189-auto-save/src/services/telegramBot/ 的 33 条命令,
通过 HTTP API 调用后端,支持所有 AstrBot 平台。
"""
from __future__ import annotations

import re

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

from .api.client import Cloud189ApiClient
from .api.errors import friendly_error
from .core.auth import is_admin, is_allowed
from .core.session import SessionStore
from .handlers import basics, folders, pt, search, share
from .handlers import stats_logs_subs as sls
from .handlers import tasks as tasks_handler


@register(
    "astrbot_plugin_cloud189_auto_save",
    "cloud189-auto-save",
    "天翼云盘自动转存系统 - 全平台机器人(完整复刻 TG bot 的 33 条命令)",
    "1.0.0",
    "",
)
class Cloud189Plugin(Star):
    def __init__(self, context: Context, config) -> None:
        super().__init__(context)
        self.config = config
        self.api = Cloud189ApiClient(
            base_url=str(config.get("api_base_url") or "http://localhost:3000"),
            api_key=str(config.get("api_key") or ""),
            timeout=int(config.get("request_timeout_seconds") or 30),
        )
        self.sessions = SessionStore(
            idle_seconds=int(config.get("session_idle_seconds") or 1800),
        )
        # 延迟启动定时清理(在第一次命令触发时启动事件循环)

    # ───────────── meta helpers ─────────────
    def is_allowed(self, sender: str) -> bool:
        return is_allowed(sender, self.config.get("allowed_user_ids") or [])

    def is_admin(self, sender: str) -> bool:
        return is_admin(sender, self.config.get("admin_user_ids") or [])

    async def terminate(self) -> None:
        try:
            await self.api.close()
        finally:
            self.sessions.stop()

    def _kick_sweeper(self) -> None:
        # 每次命令进入时确保清理任务已启动
        self.sessions.start()

    # ─────────────────── basics ───────────────────
    @filter.command("start")
    async def cmd_start(self, event: AstrMessageEvent):
        """欢迎与上手指引"""
        self._kick_sweeper()
        async for r in basics.handle_start(self, event):
            yield r

    @filter.command("help", alias={"帮助"})
    async def cmd_help(self, event: AstrMessageEvent):
        """显示命令帮助"""
        self._kick_sweeper()
        async for r in basics.handle_help(self, event):
            yield r

    @filter.command("accounts")
    async def cmd_accounts(self, event: AstrMessageEvent):
        """切换天翼云盘账号"""
        self._kick_sweeper()
        async for r in basics.handle_accounts(self, event):
            yield r

    @filter.command("cancel")
    async def cmd_cancel(self, event: AstrMessageEvent):
        """取消当前操作"""
        self._kick_sweeper()
        async for r in basics.handle_cancel(self, event):
            yield r

    @filter.command("silent")
    async def cmd_silent(self, event: AstrMessageEvent, arg: str = ""):
        """静默模式开关:/silent on|off"""
        self._kick_sweeper()
        async for r in basics.handle_silent(self, event, arg):
            yield r

    @filter.command("cloud189_ping")
    async def cmd_ping(self, event: AstrMessageEvent):
        """健康检查后端"""
        self._kick_sweeper()
        if not self.is_allowed(str(event.get_sender_id())):
            yield event.plain_result("🚫 你没有使用本机器人的权限")
            return
        try:
            data = await self.api.version()
        except Exception as exc:
            yield event.plain_result(friendly_error(exc))
            return
        yield event.plain_result(f"✅ 后端可达,version = {data}")

    # ─────────────────── tasks ───────────────────
    @filter.command("tasks")
    async def cmd_tasks(self, event: AstrMessageEvent, page: str = ""):
        """任务列表(分页:/tasks 2)"""
        self._kick_sweeper()
        async for r in tasks_handler.handle_tasks(self, event, page):
            yield r

    @filter.command("tasks_failed")
    async def cmd_tasks_failed(self, event: AstrMessageEvent, page: str = ""):
        """失败任务"""
        self._kick_sweeper()
        async for r in tasks_handler.handle_tasks_status(self, event, "failed", page):
            yield r

    @filter.command("tasks_pending")
    async def cmd_tasks_pending(self, event: AstrMessageEvent, page: str = ""):
        """待执行任务"""
        self._kick_sweeper()
        async for r in tasks_handler.handle_tasks_status(self, event, "pending", page):
            yield r

    @filter.command("tasks_processing")
    async def cmd_tasks_processing(self, event: AstrMessageEvent, page: str = ""):
        """执行中任务"""
        self._kick_sweeper()
        async for r in tasks_handler.handle_tasks_status(self, event, "processing", page):
            yield r

    @filter.command("execute_all")
    async def cmd_execute_all(self, event: AstrMessageEvent):
        """执行所有任务(管理员)"""
        self._kick_sweeper()
        async for r in tasks_handler.handle_execute_all(self, event):
            yield r

    # ── 带 ID 后缀的命令(/execute_42 /detail_42 等)用 regex 拦截 ──
    # AstrBot 在不同前缀模式下传给 regex 的 message_str 可能含或不含前导 /,
    # 统一用 ^/? 匹配两种形态。
    @filter.regex(r"^/?execute_\d+$")
    async def cmd_execute_id(self, event: AstrMessageEvent):
        """执行指定任务 /execute_<id>"""
        self._kick_sweeper()
        async for r in tasks_handler.handle_execute(self, event, _last_token(event)):
            yield r

    @filter.regex(r"^/?detail_\d+$")
    async def cmd_detail_id(self, event: AstrMessageEvent):
        """任务详情 /detail_<id>"""
        self._kick_sweeper()
        async for r in tasks_handler.handle_detail(self, event, _last_token(event)):
            yield r

    @filter.regex(r"^/?strm_\d+$")
    async def cmd_strm_id(self, event: AstrMessageEvent):
        """生成 STRM /strm_<id>"""
        self._kick_sweeper()
        async for r in tasks_handler.handle_strm(self, event, _last_token(event)):
            yield r

    @filter.regex(r"^/?emby_\d+$")
    async def cmd_emby_id(self, event: AstrMessageEvent):
        """通知 Emby /emby_<id>"""
        self._kick_sweeper()
        async for r in tasks_handler.handle_emby(self, event, _last_token(event)):
            yield r

    @filter.regex(r"^/?retry_\d+$")
    async def cmd_retry_id(self, event: AstrMessageEvent):
        """重试任务 /retry_<id>(管理员)"""
        self._kick_sweeper()
        async for r in tasks_handler.handle_retry(self, event, _last_token(event)):
            yield r

    @filter.regex(r"^/?dt_\d+$")
    async def cmd_delete_id(self, event: AstrMessageEvent):
        """删除任务 /dt_<id>(管理员)"""
        self._kick_sweeper()
        async for r in tasks_handler.handle_delete(self, event, _last_token(event)):
            yield r

    # ─────────────────── folders ───────────────────
    @filter.command("fl")
    async def cmd_fl(self, event: AstrMessageEvent):
        """常用目录列表"""
        self._kick_sweeper()
        async for r in folders.handle_fl(self, event):
            yield r

    @filter.command("fs")
    async def cmd_fs(self, event: AstrMessageEvent):
        """添加常用目录(目录树多轮浏览)"""
        self._kick_sweeper()
        async for r in folders.handle_fs(self, event):
            yield r

    @filter.regex(r"^/?df_-?\d+$")
    async def cmd_df_id(self, event: AstrMessageEvent):
        """删除常用目录 /df_<id>(管理员)"""
        self._kick_sweeper()
        async for r in folders.handle_df(self, event, _last_token(event)):
            yield r

    # ─────────────────── search / series ───────────────────
    @filter.command("search_cs")
    async def cmd_search_cs(self, event: AstrMessageEvent):
        """进入 CloudSaver 搜索模式"""
        self._kick_sweeper()
        async for r in search.handle_search_cs(self, event):
            yield r

    @filter.command("tmdb")
    async def cmd_tmdb(self, event: AstrMessageEvent, *args):
        """TMDB 搜索 /tmdb 标题 [年]"""
        self._kick_sweeper()
        query = " ".join(str(a) for a in args).strip()
        async for r in search.handle_tmdb(self, event, query):
            yield r

    @filter.command("series")
    async def cmd_series(self, event: AstrMessageEvent, *args):
        """自动追剧(正常任务)/series 剧名 [年份]"""
        self._kick_sweeper()
        query = " ".join(str(a) for a in args).strip()
        async for r in search.handle_series(self, event, query, "normal"):
            yield r

    @filter.command("lazy_series")
    async def cmd_lazy_series(self, event: AstrMessageEvent, *args):
        """自动追剧(懒转存STRM)/lazy_series 剧名 [年份]"""
        self._kick_sweeper()
        query = " ".join(str(a) for a in args).strip()
        async for r in search.handle_series(self, event, query, "lazy"):
            yield r

    # ─────────────────── stats / logs / subs ───────────────────
    @filter.command("stats")
    async def cmd_stats(self, event: AstrMessageEvent):
        """系统统计"""
        self._kick_sweeper()
        async for r in sls.handle_stats(self, event):
            yield r

    @filter.command("logs")
    async def cmd_logs(self, event: AstrMessageEvent, task_id: str = ""):
        """查看日志(限同机部署)/logs [task_id]"""
        self._kick_sweeper()
        async for r in sls.handle_logs(self, event, task_id):
            yield r

    @filter.regex(r"^/?logs_\d+$")
    async def cmd_logs_id(self, event: AstrMessageEvent):
        """查看任务日志 /logs_<id>"""
        self._kick_sweeper()
        async for r in sls.handle_logs(self, event, _last_token(event)):
            yield r

    @filter.command("subs")
    async def cmd_subs(self, event: AstrMessageEvent, page: str = ""):
        """订阅列表 /subs [page]"""
        self._kick_sweeper()
        async for r in sls.handle_subs(self, event, page):
            yield r

    @filter.regex(r"^/?subs_refresh_\d+$")
    async def cmd_subs_refresh(self, event: AstrMessageEvent):
        """刷新订阅 /subs_refresh_<id>"""
        self._kick_sweeper()
        async for r in sls.handle_subs_refresh(self, event, _last_token(event)):
            yield r

    # ─────────────────── PT ───────────────────
    @filter.command("pt_search")
    async def cmd_pt_search(self, event: AstrMessageEvent):
        """进入 PT 搜索模式"""
        self._kick_sweeper()
        async for r in pt.handle_pt_search(self, event):
            yield r

    @filter.command("pt_subs")
    async def cmd_pt_subs(self, event: AstrMessageEvent, page: str = ""):
        """PT 订阅列表"""
        self._kick_sweeper()
        async for r in pt.handle_pt_subs(self, event, page):
            yield r

    @filter.regex(r"^/?pt_detail_\d+$")
    async def cmd_pt_detail(self, event: AstrMessageEvent):
        """PT 订阅详情 /pt_detail_<id>"""
        self._kick_sweeper()
        async for r in pt.handle_pt_detail(self, event, _last_token(event)):
            yield r

    @filter.regex(r"^/?pt_refresh_\d+$")
    async def cmd_pt_refresh(self, event: AstrMessageEvent):
        """刷新 PT 订阅 /pt_refresh_<id>(管理员)"""
        self._kick_sweeper()
        async for r in pt.handle_pt_refresh(self, event, _last_token(event)):
            yield r

    @filter.regex(r"^/?pt_toggle_\d+$")
    async def cmd_pt_toggle(self, event: AstrMessageEvent):
        """启用/禁用 PT 订阅 /pt_toggle_<id>(管理员)"""
        self._kick_sweeper()
        async for r in pt.handle_pt_toggle(self, event, _last_token(event)):
            yield r

    @filter.regex(r"^/?pt_releases_\d+(?:\s+\d+)?$")
    async def cmd_pt_releases(self, event: AstrMessageEvent):
        """查看 PT Release /pt_releases_<id> [page]"""
        self._kick_sweeper()
        text = (event.message_str or "").strip()
        parts = text.split()
        token = parts[0]
        page = parts[1] if len(parts) > 1 else None
        async for r in pt.handle_pt_releases(self, event, token, page):
            yield r

    @filter.regex(r"^/?pt_retry_\d+$")
    async def cmd_pt_retry(self, event: AstrMessageEvent):
        """Release 重试 /pt_retry_<id>(管理员)"""
        self._kick_sweeper()
        async for r in pt.handle_pt_retry(self, event, _last_token(event)):
            yield r

    @filter.regex(r"^/?pt_del_\d+$")
    async def cmd_pt_del(self, event: AstrMessageEvent):
        """Release 删除 /pt_del_<id>(管理员)"""
        self._kick_sweeper()
        async for r in pt.handle_pt_del(self, event, _last_token(event)):
            yield r

    # ─────────────────── 分享链接自动识别 ───────────────────
    @filter.regex(r"cloud\.189\.cn")
    async def on_share_link(self, event: AstrMessageEvent):
        """检测到 cloud.189.cn 分享链接时自动处理"""
        # 命令以 / 开头的不处理(避免与 /search_cs 等冲突)
        text = (event.message_str or "").strip()
        if text.startswith("/"):
            return
        self._kick_sweeper()
        async for r in share.handle_share_link(self, event):
            yield r


def _last_token(event: AstrMessageEvent) -> str:
    text = (event.message_str or "").strip()
    return text.split()[0] if text else ""

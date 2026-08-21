"""HTTP 客户端:封装 cloud189-auto-save 后端的全部 REST 端点。

后端鉴权:请求头 `x-api-key: <system.apiKey>`,可绕过 session 登录
(见 `cloud189-auto-save/src/index.js:402-405`)。

大多数 200 返回包形如 ``{ success: bool, data?: any, error?: str }``；
少数端点还会在同级返回 ``message`` 或 ``transferStats``。客户端默认解包
``data``，需要同级元数据的调用可保留完整响应，失败统一抛 :class:`ApiError`。
"""
from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .errors import ApiError


class Cloud189ApiClient:
    def __init__(self, base_url: str, api_key: str, timeout: int = 30) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or ""
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None
        self._lock = asyncio.Lock()

    # ─────────────── infra ───────────────
    async def _ensure(self) -> aiohttp.ClientSession:
        if self._session and not self._session.closed:
            return self._session
        async with self._lock:
            if self._session and not self._session.closed:
                return self._session
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["x-api-key"] = self.api_key
            self._session = aiohttp.ClientSession(timeout=self._timeout, headers=headers)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    async def request(
        self,
        method: str,
        path: str,
        *,
        params=None,
        json=None,
        unwrap: bool = True,
    ) -> Any:
        if not self.base_url:
            raise ApiError("插件未配置 api_base_url")
        session = await self._ensure()
        url = f"{self.base_url}{path}"
        try:
            async with session.request(method, url, params=params, json=json) as resp:
                # 后端总是返回 application/json,但有些路径直接返回数组,所以放宽
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    text = await resp.text()
                    if resp.status >= 400:
                        raise ApiError(text or resp.reason, status=resp.status)
                    return text

                if resp.status >= 400:
                    err = data.get("error") if isinstance(data, dict) else None
                    raise ApiError(err or resp.reason or f"HTTP {resp.status}", status=resp.status)

                if isinstance(data, dict) and "success" in data:
                    if not data.get("success"):
                        raise ApiError(data.get("error") or "请求失败", status=resp.status)
                    if not unwrap:
                        return data
                    if "data" in data:
                        return data.get("data")
                    payload = {key: value for key, value in data.items() if key != "success"}
                    return payload or None
                return data
        except aiohttp.ClientError as exc:
            raise ApiError(f"网络错误: {exc}") from exc
        except asyncio.TimeoutError as exc:
            raise ApiError("请求超时") from exc

    # ─────────────── version / health ───────────────
    async def version(self) -> dict:
        return await self.request("GET", "/api/version")

    # ─────────────── accounts ───────────────
    async def list_accounts(self) -> list[dict]:
        data = await self.request("GET", "/api/accounts")
        return data or []

    async def set_default_account(self, account_id: int) -> Any:
        return await self.request("PUT", f"/api/accounts/{account_id}/default")

    # ─────────────── tasks ───────────────
    async def list_tasks(
        self,
        *,
        status: str | None = None,
        account_id: int | None = None,
        keyword: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        params: dict[str, Any] = {}
        if status:
            params["status"] = status
        if account_id:
            params["accountId"] = account_id
        if keyword:
            params["search"] = keyword
        if limit:
            params["page"] = 1
            params["pageSize"] = max(1, min(int(limit), 200))
        data = await self.request("GET", "/api/tasks", params=params or None)
        # 后端有时返回 list,有时返回 {tasks, total}
        if isinstance(data, dict) and "tasks" in data:
            return data["tasks"] or []
        return data or []

    async def get_task(self, task_id: int | str) -> dict | None:
        # 后端没有 GET /api/tasks/:id;复用 list_tasks 后过滤
        tasks = await self.list_tasks()
        target_id = str(task_id)
        for task in tasks:
            if str(task.get("id")) == target_id:
                return task
        return None

    async def create_task(self, payload: dict) -> Any:
        return await self.request("POST", "/api/tasks", json=payload)

    async def execute_task(self, task_id: int | str) -> Any:
        return await self.request("POST", f"/api/tasks/{task_id}/execute")

    async def execute_all(self) -> Any:
        return await self.request("POST", "/api/tasks/executeAll")

    async def update_task(self, task_id: int | str, payload: dict) -> Any:
        return await self.request("PUT", f"/api/tasks/{task_id}", json=payload)

    async def delete_task(self, task_id: int | str, *, delete_cloud: bool = False) -> Any:
        params = {"deleteCloud": "true"} if delete_cloud else None
        return await self.request("DELETE", f"/api/tasks/{task_id}", params=params)

    async def make_strm(self, task_ids: list[int | str], *, overwrite: bool = False) -> Any:
        return await self.request(
            "POST",
            "/api/tasks/strm",
            json={"taskIds": [int(t) for t in task_ids], "overwrite": overwrite},
        )

    # ─────────────── folders / favorites / share ───────────────
    async def list_folders(self, account_id: int, *, folder_id: str = "-11", refresh: bool = False) -> list[dict]:
        params: dict[str, Any] = {"folderId": folder_id}
        if refresh:
            params["refresh"] = "true"
        data = await self.request("GET", f"/api/folders/{account_id}", params=params)
        return data or []

    async def list_favorites(self, account_id: int) -> list[dict]:
        data = await self.request("GET", f"/api/favorites/{account_id}")
        return data or []

    async def save_favorite(self, payload: dict) -> Any:
        return await self.request("POST", "/api/saveFavorites", json=payload)

    async def parse_share(self, account_id: int, share_link: str, access_code: str | None = None) -> Any:
        payload = {"accountId": account_id, "shareLink": share_link}
        if access_code:
            payload["accessCode"] = access_code
        return await self.request("POST", "/api/share/parse", json=payload)

    # ─────────────── cloudsaver / tmdb / series ───────────────
    async def cloudsaver_search(self, keyword: str) -> list[dict]:
        data = await self.request("GET", "/api/cloudsaver/search", params={"keyword": keyword})
        return data or []

    async def auto_series(self, *, title: str, year: str | None, mode: str = "normal") -> dict:
        return await self.request("POST", "/api/auto-series", json={"title": title, "year": year, "mode": mode})

    async def auto_series_settings(self) -> dict:
        data = await self.request("GET", "/api/auto-series/settings")
        return data or {}

    async def auto_series_intents(self) -> list[dict]:
        data = await self.request("GET", "/api/auto-series/intents")
        return data or []

    async def auto_series_intent_action(self, intent_id: str, action: str) -> Any:
        if action not in {"pause", "resume", "run"}:
            raise ValueError("自动追剧操作必须是 pause、resume 或 run")
        return await self.request("POST", f"/api/auto-series/intents/{intent_id}/{action}")

    async def tmdb_search(self, keyword: str, year: str | None = None) -> dict:
        params: dict[str, Any] = {"keyword": keyword}
        if year:
            params["year"] = year
        return await self.request("GET", "/api/tmdb/search", params=params)

    # ─────────────── HDHive ───────────────
    async def hdhive_status(self) -> dict:
        data = await self.request("GET", "/api/hdhive/status")
        return data or {}

    async def hdhive_search(self, keyword: str, *, limit: int = 12) -> dict:
        data = await self.request(
            "GET",
            "/api/hdhive/search",
            params={"keyword": keyword, "limit": max(1, min(int(limit), 50))},
        )
        if isinstance(data, list):
            return {"items": data}
        return data or {"items": []}

    async def hdhive_resources(self, media_type: str, tmdb_id: str | int) -> list[dict]:
        data = await self.request(
            "GET",
            "/api/hdhive/resources",
            params={"type": media_type, "tmdbId": tmdb_id},
        )
        return data or []

    async def hdhive_checkin(self) -> dict:
        data = await self.request("POST", "/api/hdhive/checkin")
        return data or {}

    # ─────────────── CloudSaver-style subscriptions ───────────────
    async def list_subscriptions(self) -> list[dict]:
        data = await self.request("GET", "/api/subscriptions")
        return data or []

    async def refresh_subscription(self, sub_id: int) -> Any:
        return await self.request("POST", f"/api/subscriptions/{sub_id}/refresh")

    # ─────────────── PT ───────────────
    async def pt_presets(self) -> list[dict]:
        data = await self.request("GET", "/api/pt/sources/presets")
        return data or []

    async def pt_search(self, preset: str, keyword: str) -> list[dict]:
        data = await self.request(
            "GET", "/api/pt/sources/search", params={"preset": preset, "keyword": keyword}
        )
        return data or []

    async def pt_groups(self, preset: str, *, bgm_id: str | int | None = None, bangumi_url: str | None = None) -> list[dict]:
        params: dict[str, Any] = {"preset": preset}
        if bgm_id:
            params["bgmId"] = bgm_id
        if bangumi_url:
            params["bangumiUrl"] = bangumi_url
        data = await self.request("GET", "/api/pt/sources/groups", params=params)
        return data or []

    async def pt_subs_list(self) -> list[dict]:
        data = await self.request("GET", "/api/pt/subscriptions")
        return data or []

    async def pt_sub_update(self, sub_id: int, payload: dict) -> Any:
        return await self.request("PUT", f"/api/pt/subscriptions/{sub_id}", json=payload)

    async def pt_sub_refresh(self, sub_id: int) -> Any:
        return await self.request("POST", f"/api/pt/subscriptions/{sub_id}/refresh")

    async def pt_sub_releases(self, sub_id: int, *, page: int = 1, page_size: int = 5) -> dict:
        data = await self.request(
            "GET",
            f"/api/pt/subscriptions/{sub_id}/releases",
            params={"page": page, "pageSize": page_size},
        )
        if isinstance(data, list):
            start = (max(1, page) - 1) * max(1, page_size)
            return {
                "releases": data[start : start + max(1, page_size)],
                "total": len(data),
            }
        return data or {"releases": [], "total": 0}

    async def pt_releases_all(self, *, limit: int = 100) -> dict:
        payload = await self.request(
            "GET",
            "/api/pt/releases",
            params={"limit": max(1, min(int(limit), 500))},
            unwrap=False,
        )
        if isinstance(payload, list):
            return {"releases": payload, "transferStats": {}}
        payload = payload or {}
        return {
            "releases": payload.get("data") or [],
            "transferStats": payload.get("transferStats") or {},
        }

    async def pt_release_retry(self, release_id: int) -> Any:
        return await self.request("POST", f"/api/pt/releases/{release_id}/retry")

    async def pt_release_delete(self, release_id: int, *, delete_files: bool = True) -> Any:
        params = {"deleteFiles": "true" if delete_files else "false"}
        return await self.request("DELETE", f"/api/pt/releases/{release_id}", params=params)

    # ─────────────── audit history ───────────────
    async def audit_runs(
        self,
        *,
        page: int = 1,
        page_size: int = 10,
        keyword: str | None = None,
        module: str | None = None,
        status: str | None = None,
    ) -> dict:
        params: dict[str, Any] = {
            "page": max(1, int(page)),
            "pageSize": max(1, min(int(page_size), 100)),
        }
        if keyword:
            params["keyword"] = keyword
        if module:
            params["module"] = module
        if status:
            params["status"] = status
        data = await self.request("GET", "/api/audit-runs", params=params)
        return data or {"items": [], "total": 0, "pages": 1, "stats": {}}

    async def audit_run_detail(self, run_id: str) -> dict:
        data = await self.request("GET", f"/api/audit-runs/{run_id}")
        return data or {}

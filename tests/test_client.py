from __future__ import annotations

import unittest
from unittest.mock import AsyncMock

from aiohttp import web

from api.client import Cloud189ApiClient


class Cloud189ApiClientTest(unittest.IsolatedAsyncioTestCase):
    async def test_pt_releases_all_keeps_transfer_stats(self):
        client = Cloud189ApiClient("http://example.test", "key")
        client.request = AsyncMock(
            return_value={
                "success": True,
                "data": [{"id": 1, "status": "downloading"}],
                "transferStats": {"downloadSpeed": 1024, "cloudUploadSpeed": 2048},
            }
        )

        result = await client.pt_releases_all(limit=999)

        self.assertEqual(result["releases"][0]["id"], 1)
        self.assertEqual(result["transferStats"]["cloudUploadSpeed"], 2048)
        client.request.assert_awaited_once_with(
            "GET",
            "/api/pt/releases",
            params={"limit": 500},
            unwrap=False,
        )

    async def test_pt_subscription_releases_are_paginated_locally(self):
        client = Cloud189ApiClient("http://example.test", "key")
        client.request = AsyncMock(return_value=[{"id": value} for value in range(1, 7)])

        result = await client.pt_sub_releases(8, page=2, page_size=2)

        self.assertEqual([item["id"] for item in result["releases"]], [3, 4])
        self.assertEqual(result["total"], 6)

    async def test_audit_filters_skip_empty_values(self):
        client = Cloud189ApiClient("http://example.test", "key")
        client.request = AsyncMock(return_value={"items": [], "total": 0})

        await client.audit_runs(page=2, page_size=500, keyword="庆余年", module="", status=None)

        client.request.assert_awaited_once_with(
            "GET",
            "/api/audit-runs",
            params={"page": 2, "pageSize": 100, "keyword": "庆余年"},
        )

    async def test_auto_series_action_rejects_unknown_action(self):
        client = Cloud189ApiClient("http://example.test", "key")

        with self.assertRaises(ValueError):
            await client.auto_series_intent_action("intent-id", "delete")

    async def test_request_preserves_success_payload_without_data_field(self):
        app = web.Application()

        async def checkin(request):
            return web.json_response({"success": True, "message": "签到成功"})

        app.router.add_post("/checkin", checkin)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        client = Cloud189ApiClient(f"http://127.0.0.1:{port}", "")
        try:
            result = await client.request("POST", "/checkin")
            self.assertEqual(result, {"message": "签到成功"})
        finally:
            await client.close()
            await runner.cleanup()


if __name__ == "__main__":
    unittest.main()

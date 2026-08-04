from __future__ import annotations

import asyncio
from typing import Any

import pytest

from hermes_oauth_proxy.adapters import ADAPTERS, get_adapter
from hermes_oauth_proxy.adapters.base import UpstreamAdapter, UpstreamCredential
from hermes_oauth_proxy.server import create_app


def test_initial_registry_contains_only_xai():
    assert set(ADAPTERS) == {"xai"}
    assert get_adapter("xai").name == "xai"


def test_unknown_adapter_is_rejected():
    with pytest.raises(ValueError, match="Unknown proxy upstream provider"):
        get_adapter("synthetic")


aiohttp = pytest.importorskip("aiohttp")
from aiohttp import web  # noqa: E402


class FakeAdapter(UpstreamAdapter):
    def __init__(self, base_url: str):
        self._base_url = base_url

    @property
    def name(self):
        return "synthetic"

    @property
    def display_name(self):
        return "Synthetic"

    @property
    def allowed_paths(self):
        return frozenset({"/chat/completions"})

    def is_authenticated(self):
        return True

    def get_credential(self):
        return UpstreamCredential(bearer="synthetic-upstream-bearer", base_url=self._base_url)


async def _start(app: web.Application):
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = next(iter(site._server.sockets)).getsockname()[1]
    return runner, f"http://127.0.0.1:{port}"


def test_proxy_replaces_client_authorization_and_preserves_body():
    async def run():
        captured: dict[str, Any] = {}

        async def upstream(request):
            captured["authorization"] = request.headers.get("Authorization")
            captured["body"] = await request.json()
            return web.json_response({"ok": True})

        upstream_app = web.Application()
        upstream_app.router.add_post("/v1/chat/completions", upstream)
        upstream_runner, upstream_base = await _start(upstream_app)
        proxy_runner, proxy_base = await _start(create_app(FakeAdapter(f"{upstream_base}/v1")))
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{proxy_base}/v1/chat/completions",
                    json={"model": "synthetic-model", "messages": []},
                    headers={"Authorization": "Bearer client-must-not-leak"},
                ) as response:
                    assert response.status == 200
                    assert await response.json() == {"ok": True}
            assert captured["authorization"] == "Bearer synthetic-upstream-bearer"
            assert captured["body"]["model"] == "synthetic-model"
        finally:
            await proxy_runner.cleanup()
            await upstream_runner.cleanup()

    asyncio.run(run())

from __future__ import annotations

import asyncio
import base64
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from hermes_composite_oauth_gateway.adapters.base import UpstreamAdapter, UpstreamCredential
from hermes_composite_oauth_gateway.adapters.composite import CompositeOAuthAdapter
from hermes_composite_oauth_gateway.adapters.openai_codex import OpenAICodexAdapter, _chatgpt_account_id
from hermes_composite_oauth_gateway.adapters.xai import XAIGrokAdapter
from hermes_composite_oauth_gateway.server import create_app


def _jwt(account_id: str) -> str:
    def encode(payload):
        raw = json.dumps(payload, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    return ".".join(
        (
            encode({"alg": "none"}),
            encode({"https://api.openai.com/auth": {"chatgpt_account_id": account_id}}),
            "synthetic-signature",
        )
    )


def test_codex_account_id_and_headers_are_derived_from_selected_token():
    token = _jwt("acct-synthetic")
    adapter = OpenAICodexAdapter()
    credential = UpstreamCredential(bearer=token, base_url="https://example.invalid/backend-api/codex")
    assert _chatgpt_account_id(token) == "acct-synthetic"
    assert adapter.request_headers(credential) == {
        "User-Agent": "codex_cli_rs/0.0.0 (Hermes Composite OAuth Gateway)",
        "originator": "codex_cli_rs",
        "ChatGPT-Account-ID": "acct-synthetic",
    }


def test_codex_401_refreshes_the_exact_failed_pool_entry():
    adapter = OpenAICodexAdapter()
    refreshed_entry = SimpleNamespace(
        runtime_api_key="fresh-token",
        access_token="fresh-token",
        runtime_base_url="https://example.invalid/backend-api/codex",
        base_url=None,
        expires_at=None,
    )
    pool = MagicMock()
    pool.try_refresh_matching.return_value = refreshed_entry
    adapter._load_pool = lambda: pool

    retry = adapter.get_retry_credential(
        failed_credential=UpstreamCredential(
            bearer="failed-token",
            base_url="https://example.invalid/backend-api/codex",
        ),
        status_code=401,
    )

    assert retry is not None
    assert retry.bearer == "fresh-token"
    pool.try_refresh_matching.assert_called_once_with(api_key_hint="failed-token")
    pool.mark_exhausted_and_rotate.assert_not_called()


@pytest.mark.parametrize("status_code", [401, 429])
def test_xai_retry_targets_the_exact_failed_credential(status_code):
    adapter = XAIGrokAdapter()
    rotated_entry = SimpleNamespace(
        runtime_api_key="rotated-token",
        access_token="rotated-token",
        runtime_base_url="https://example.invalid/v1",
        base_url=None,
        expires_at=None,
    )
    pool = MagicMock()
    if status_code == 401:
        pool.try_refresh_matching.return_value = rotated_entry
    else:
        pool.mark_exhausted_and_rotate.return_value = rotated_entry
    adapter._load_pool = lambda: pool

    retry = adapter.get_retry_credential(
        failed_credential=UpstreamCredential(
            bearer="failed-xai-token",
            base_url="https://example.invalid/v1",
        ),
        status_code=status_code,
    )

    assert retry is not None and retry.bearer == "rotated-token"
    if status_code == 401:
        pool.try_refresh_matching.assert_called_once_with(api_key_hint="failed-xai-token")
    else:
        pool.mark_exhausted_and_rotate.assert_called_once_with(
            status_code=429,
            api_key_hint="failed-xai-token",
        )


class StaticAdapter(UpstreamAdapter):
    def __init__(self, name: str, prefix: str, base_url: str, bearer: str, paths):
        self._name = name
        self._prefix = prefix
        self._base_url = base_url
        self._bearer = bearer
        self._paths = frozenset(paths)

    @property
    def name(self):
        return self._name

    @property
    def display_name(self):
        return self._name

    @property
    def allowed_paths(self):
        return self._paths

    def owns_model(self, model: str) -> bool:
        return model.startswith(self._prefix)

    def is_authenticated(self):
        return True

    def get_credential(self):
        return UpstreamCredential(bearer=self._bearer, base_url=self._base_url)


class StaticCodexAdapter(OpenAICodexAdapter):
    def __init__(self, base_url: str, bearer: str):
        self._base_url = base_url
        self._bearer = bearer

    def is_authenticated(self):
        return True

    def get_credential(self):
        return UpstreamCredential(bearer=self._bearer, base_url=self._base_url)


@pytest.fixture
def adapters():
    xai = StaticAdapter(
        "xai",
        "grok-",
        "https://xai.example.invalid/v1",
        "xai-synthetic-token",
        {"/responses", "/chat/completions", "/models"},
    )
    codex = StaticCodexAdapter(
        "https://codex.example.invalid/backend-api/codex",
        _jwt("acct-synthetic"),
    )
    return xai, codex


def test_composite_routes_by_model_and_rejects_unknown_models(adapters):
    xai, codex = adapters
    router = CompositeOAuthAdapter((xai, codex))
    assert router.select_adapter("/responses", b'{"model":"grok-4"}') is xai
    assert router.select_adapter("/responses", b'{"model":"gpt-5.6-sol"}') is codex
    with pytest.raises(ValueError, match="No configured OAuth upstream owns model"):
        router.select_adapter("/responses", b'{"model":"other-model"}')
    with pytest.raises(ValueError, match="model is required"):
        router.select_adapter("/responses", b"{}")


aiohttp = pytest.importorskip("aiohttp")
from aiohttp import web  # noqa: E402


async def _start(app: web.Application):
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = next(iter(site._server.sockets)).getsockname()[1]
    return runner, f"http://127.0.0.1:{port}"


def test_composite_end_to_end_routing_headers_and_merged_models():
    async def run():
        captured = []

        async def responses(request):
            captured.append(
                {
                    "path": request.path,
                    "authorization": request.headers.get("Authorization"),
                    "account": request.headers.get("ChatGPT-Account-ID"),
                    "originator": request.headers.get("originator"),
                    "user_agent": request.headers.get("User-Agent"),
                    "body": await request.json(),
                }
            )
            return web.json_response({"ok": True, "path": request.path})

        async def xai_models(request):
            return web.json_response(
                {
                    "object": "list",
                    "data": [
                        {"id": "grok-synthetic", "object": "model"},
                        {"id": "unexpected-model-id", "object": "model"},
                    ],
                }
            )

        async def codex_models(request):
            captured.append(
                {
                    "path": request.path,
                    "query": request.query_string,
                    "account": request.headers.get("ChatGPT-Account-ID"),
                    "originator": request.headers.get("originator"),
                }
            )
            return web.json_response(
                {
                    "models": [
                        {"slug": "gpt-synthetic", "priority": 1},
                        {"slug": "gpt-hidden", "priority": 0, "visibility": "hidden"},
                    ]
                }
            )

        upstream = web.Application()
        upstream.router.add_post("/v1/responses", responses)
        upstream.router.add_get("/v1/models", xai_models)
        upstream.router.add_post("/backend-api/codex/responses", responses)
        upstream.router.add_get("/backend-api/codex/models", codex_models)
        upstream_runner, upstream_base = await _start(upstream)

        xai = StaticAdapter(
            "xai",
            "grok-",
            f"{upstream_base}/v1",
            "xai-synthetic-token",
            {"/responses", "/chat/completions", "/models"},
        )
        codex = StaticCodexAdapter(
            f"{upstream_base}/backend-api/codex",
            _jwt("acct-synthetic"),
        )
        proxy_runner, proxy_base = await _start(create_app(CompositeOAuthAdapter((xai, codex))))
        try:
            async with aiohttp.ClientSession() as session:
                for model in ("grok-synthetic", "gpt-synthetic"):
                    async with session.post(
                        f"{proxy_base}/v1/responses",
                        json={"model": model, "input": "synthetic"},
                        headers={
                            "Authorization": "Bearer client-must-not-leak",
                            "ChatGPT-Account-ID": "client-account-must-not-leak",
                            "originator": "client-origin-must-not-leak",
                        },
                    ) as response:
                        assert response.status == 200
                        await response.read()

                async with session.get(f"{proxy_base}/v1/responses") as response:
                    assert response.status == 405
                async with session.post(f"{proxy_base}/v1/models") as response:
                    assert response.status == 405

                async with session.get(
                    f"{proxy_base}/v1/models",
                    headers={"Authorization": "Bearer local-placeholder"},
                ) as response:
                    assert response.status == 200
                    model_payload = await response.json()
        finally:
            await proxy_runner.cleanup()
            await upstream_runner.cleanup()

        xai_request, codex_request, codex_catalog = captured
        assert xai_request["path"] == "/v1/responses"
        assert xai_request["authorization"] == "Bearer xai-synthetic-token"
        assert xai_request["account"] is None
        assert xai_request["originator"] is None

        assert codex_request["path"] == "/backend-api/codex/responses"
        assert codex_request["authorization"].startswith("Bearer ")
        assert "client-must-not-leak" not in codex_request["authorization"]
        assert codex_request["account"] == "acct-synthetic"
        assert codex_request["originator"] == "codex_cli_rs"
        assert codex_request["user_agent"].startswith("codex_cli_rs/")

        assert codex_catalog == {
            "path": "/backend-api/codex/models",
            "query": "client_version=1.0.0",
            "account": "acct-synthetic",
            "originator": "codex_cli_rs",
        }
        assert model_payload == {
            "object": "list",
            "data": [
                {"id": "grok-synthetic", "object": "model", "created": 0, "owned_by": "xai"},
                {
                    "id": "gpt-synthetic",
                    "object": "model",
                    "created": 0,
                    "owned_by": "openai-codex",
                },
            ],
        }

    asyncio.run(run())


def test_server_retries_once_with_rotated_credential_after_401():
    class RotatingAdapter(StaticAdapter):
        def get_retry_credential(self, *, failed_credential, status_code):
            assert failed_credential.bearer == "expired-synthetic-token"
            assert status_code == 401
            return UpstreamCredential(
                bearer="refreshed-synthetic-token",
                base_url=self._base_url,
            )

    async def run():
        seen = []

        async def responses(request):
            authorization = request.headers.get("Authorization")
            seen.append(authorization)
            if authorization == "Bearer expired-synthetic-token":
                return web.json_response({"error": "expired"}, status=401)
            return web.json_response({"ok": True})

        upstream = web.Application()
        upstream.router.add_post("/v1/responses", responses)
        upstream_runner, upstream_base = await _start(upstream)
        adapter = RotatingAdapter(
            "xai",
            "grok-",
            f"{upstream_base}/v1",
            "expired-synthetic-token",
            {"/responses"},
        )
        proxy_runner, proxy_base = await _start(create_app(adapter))
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{proxy_base}/v1/responses",
                    json={"model": "grok-synthetic", "input": "synthetic"},
                ) as response:
                    assert response.status == 200
                    assert await response.json() == {"ok": True}
        finally:
            await proxy_runner.cleanup()
            await upstream_runner.cleanup()

        assert seen == [
            "Bearer expired-synthetic-token",
            "Bearer refreshed-synthetic-token",
        ]

    asyncio.run(run())

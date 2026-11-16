# Hermes Composite OAuth Gateway

A loopback-only, model-aware OAuth subscription gateway backed by credentials managed by [Hermes Agent](https://github.com/NousResearch/hermes-agent).

It lets multiple local Hermes profiles and sessions share canonical OAuth credentials without copying refresh tokens into every profile.

## Current adapters

| Adapter | Model ownership | Forwarded API paths | Credential source |
|---|---|---|---|
| xAI Grok OAuth | `grok-*` | `/v1/chat/completions`, `/v1/responses`, `/v1/models`, embeddings and image endpoints | Hermes `xai-oauth` pool |
| OpenAI Codex OAuth | `gpt-*`, `codex-*` | `/v1/responses`, `/v1/models` | Hermes `openai-codex` pool |
| Composite gateway | model-aware dispatch to both adapters | union of both adapters; merged `/v1/models` | both pools |

The gateway never translates Chat Completions into Responses. Each logical Hermes provider must retain the API mode its upstream expects.

## Security boundary

- The default listener is `127.0.0.1:8645`.
- Non-loopback binding is rejected. There is no unsafe override.
- Any client bearer value is discarded and replaced with the selected canonical OAuth access token.
- Provider-owned headers such as `ChatGPT-Account-ID` and `originator` are stripped from client input and reconstructed from the selected Codex credential.
- Refresh tokens and account state remain in Hermes Agent's credential store. They are not copied into this repository or consumer profiles.
- Because any local client can use the proxy, do not expose it to a LAN, container bridge, reverse proxy, or public socket without adding real client authentication.

## Requirements

- Python 3.11+
- Hermes Agent installed and authenticated
- `aiohttp`

Authenticate the canonical providers first:

```bash
hermes auth add xai-oauth
hermes auth add openai-codex
```

## Install from GitHub

Install into the same Python environment that provides Hermes Agent's `agent` and `hermes_cli` packages:

```bash
git clone https://github.com/vforge-labs/hermes-composite-oauth-gateway.git
cd hermes-composite-oauth-gateway
python -m pip install .
```

For source-tree development, include both repositories on `PYTHONPATH`:

```bash
export PYTHONPATH=/path/to/hermes-agent:/path/to/hermes-composite-oauth-gateway
python -m hermes_composite_oauth_gateway status
```

### Persistent service deployment

For a long-running service, avoid relying only on a wheel installed into Hermes Agent's managed virtualenv: that environment may be regenerated during an Agent update, removing locally installed packages. Keep this gateway checkout in a stable directory and run its module from the Hermes virtualenv, with both source trees on `PYTHONPATH`. The example unit assumes the gateway is cloned to `~/src/hermes-composite-oauth-gateway` and Hermes Agent is checked out at `~/.hermes/hermes-agent`; edit those paths in the unit if your installation differs.

```bash
git clone https://github.com/vforge-labs/hermes-composite-oauth-gateway.git \
  ~/src/hermes-composite-oauth-gateway
```

Install `examples/hermes-composite-oauth-gateway.service` under `~/.config/systemd/user/`, then verify the resolved `PYTHONPATH`, `ExecStart`, Python environment, and `/health` before enabling or restarting any production service. The unit uses the repository's `python -m hermes_composite_oauth_gateway` entry point, so it does not depend on the gateway distribution remaining installed inside Hermes' managed virtualenv.

## Run safely

Prove the new gateway on a temporary loopback port before changing any service:

```bash
hermes-composite-oauth-gateway start \
  --provider composite \
  --host 127.0.0.1 \
  --port 18645
```

Check health and merged discovery:

```bash
curl -fsS http://127.0.0.1:18645/health
curl -fsS -H 'Authorization: Bearer local-placeholder' \
  http://127.0.0.1:18645/v1/models
```

The placeholder bearer is required by some OpenAI-compatible clients but is never forwarded upstream.

## Hermes provider configuration

Keep two logical providers even though they share one listener:

```yaml
providers:
  xai-oauth-proxy:
    api: http://127.0.0.1:8645/v1
    api_key: local-placeholder
    transport: chat_completions

  openai-codex-proxy:
    api: http://127.0.0.1:8645/v1
    api_key: local-placeholder
    transport: codex_responses
```

Use `xai-oauth-proxy/grok-*` for Grok and `openai-codex-proxy/gpt-*` for Codex. The model-aware gateway remains the final routing authority.

## Codex request contract

The ChatGPT Codex backend is not ordinary OpenAI Chat Completions:

- send Responses requests to `/v1/responses`;
- include `model`, `instructions`, and Responses-format `input`;
- set `store: false`;
- set `stream: true`;
- do not assume every public OpenAI Responses parameter is accepted. In the verified backend, `max_output_tokens` was rejected.

The proxy forwards this contract transparently. It does not silently rewrite invalid payloads.

## Verification

```bash
python -m pytest -q
ruff check .
python -m build --wheel
```

The test suite uses synthetic credentials only. See [`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md) for temporary-port live acceptance and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for routing and refresh behavior.

Contributions should follow [`CONTRIBUTING.md`](CONTRIBUTING.md). Security issues belong in GitHub's private vulnerability-reporting surface; see [`SECURITY.md`](SECURITY.md).

## Provenance

The initial xAI proxy modules were extracted from Hermes Agent and retain the upstream MIT license. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).

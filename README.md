# Hermes OAuth Proxy

A loopback-only OAuth subscription proxy backed by credentials managed by [Hermes Agent](https://github.com/NousResearch/hermes-agent).

This standalone source tree was extracted from Hermes Agent's built-in subscription proxy so it can evolve independently and later be contributed upstream. The initial `0.1.0` baseline supports xAI Grok OAuth and intentionally preserves the built-in proxy's credential-pool behavior.

## Security boundary

The proxy accepts any client bearer and replaces it with the selected Hermes-managed upstream credential. It therefore **must remain loopback-only** unless an operator adds a real authentication and network-security layer. Request bodies are forwarded, not logged.

## Requirements

- Python 3.11+
- Hermes Agent installed in the same Python environment
- `aiohttp`
- A Hermes-managed xAI OAuth login (`hermes auth add xai-oauth --type oauth`)

## Development run

```bash
export PYTHONPATH=/path/to/hermes-agent:/path/to/hermes-oauth-proxy
python -m hermes_oauth_proxy providers
python -m hermes_oauth_proxy start --provider xai --host 127.0.0.1 --port 8645
```

Clients use an OpenAI-compatible endpoint:

```text
Base URL: http://127.0.0.1:8645/v1
API key:  any non-empty local placeholder
```

## Service example

See [`examples/hermes-oauth-proxy.service`](examples/hermes-oauth-proxy.service). Replace placeholders with installation-specific paths. Do not expose the listener on `0.0.0.0` by default.

## Roadmap

- OpenAI Codex OAuth adapter
- Composite model-aware routing behind one listener
- Merged model catalog
- Additional protocol-compatible OAuth adapters

## Provenance and license

The baseline proxy implementation is derived from Hermes Agent, copyright Nous Research, under the MIT License. See [NOTICE](NOTICE) and [LICENSE](LICENSE). This community-maintained repository is not an official Nous Research release.

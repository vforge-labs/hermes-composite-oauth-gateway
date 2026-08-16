# Contributing

Contributions are welcome, especially new provider adapters, Hermes compatibility fixes, and security/concurrency regression tests.

## Ground rules

- Never include OAuth tokens, auth stores, decoded claims, account IDs, profile configuration, logs, hostnames, IP addresses, or `$HERMES_HOME` contents in issues, fixtures, or commits.
- Use synthetic credentials and loopback-only fake upstreams in tests.
- Preserve loopback-only binding and fail closed on unsupported paths, methods, unknown models, and ambiguous model ownership.
- Client authorization and provider-owned identity headers must never reach an upstream unchanged.
- Keep credential resolution and refresh logic inside provider adapters.
- New retry or streaming paths need cancellation, disconnect, and cleanup coverage.

## Development setup

Clone this repository and a compatible Hermes Agent checkout:

```bash
git clone https://github.com/vforge-labs/hermes-composite-oauth-gateway.git
git clone https://github.com/NousResearch/hermes-agent.git
cd hermes-composite-oauth-gateway
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip pytest ruff build aiohttp
export PYTHONPATH="../hermes-agent:$PWD"
```

Run the harness:

```bash
python -m pytest
ruff check .
python -m build --wheel
```

## Pull requests

Include the Hermes commit(s) tested, provider-contract assumptions, tests added or updated, security/concurrency impact, and confirmation that fixtures contain synthetic data only.

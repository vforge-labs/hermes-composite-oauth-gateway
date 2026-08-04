# Maintainer and agent instructions

This repository contains a standalone OAuth proxy that reuses Hermes Agent credential resolvers.

## Invariants

- Never commit OAuth state, API keys, tokens, `$HERMES_HOME`, profile files, logs, hostnames, IP addresses, account IDs, or household-specific paths.
- Tests use synthetic credentials and loopback-only fake upstreams.
- Default binding remains `127.0.0.1`; broad binding requires an explicit operator security design.
- Client `Authorization` headers are discarded before forwarding.
- Provider-specific authentication and headers stay inside their adapters.
- The deployed service is not modified from this repository without a separate verified cutover.

## Verification

Run `python -m pytest`, `ruff check .`, build a wheel, inspect its contents, and scan tracked files for credentials and environment identifiers before publication. Test against both the pinned compatible Hermes checkout and current upstream where possible.

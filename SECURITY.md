# Security policy

## Supported use

Hermes OAuth Proxy is intended for a single-user machine and a loopback-only listener.

## Important boundary

The client `Authorization` value is a compatibility placeholder, not client authentication. Any process that can reach the listener can use the configured OAuth subscriptions.

Do not expose the proxy through:

- `0.0.0.0` or a LAN interface;
- Docker or VM bridge publishing;
- a reverse proxy;
- SSH remote forwarding;
- public tunnels.

Those deployments require independent client authentication, authorization, rate limiting, and audit design.

## Credential handling

- OAuth credentials are loaded from Hermes Agent at runtime.
- No token, account ID, auth file, or machine-specific config belongs in Git.
- Client-supplied authorization and provider identity headers are stripped.
- Logs must not print bearer values or decoded OAuth claims.
- Private rollback archives must be permission-restricted and kept outside the repository.

## Reporting

Report vulnerabilities privately to the repository maintainer. Do not include live tokens, auth files, or account identifiers in reports.

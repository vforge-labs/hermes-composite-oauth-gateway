# Architecture

## Purpose

One loopback listener fronts several OAuth subscription backends while each provider retains an isolated adapter and canonical Hermes credential pool.

```text
Hermes profile A ─┐
Hermes profile B ─┼─> 127.0.0.1:8645/v1 ─> composite router
Hermes profile N ─┘                              ├─ grok-*  ─> xAI OAuth
                                                 └─ gpt-*   ─> OpenAI Codex OAuth
```

Consumer profiles contain only a local placeholder key. Refresh tokens stay with the canonical Hermes home.

## Request flow

1. Accept a request only under `/v1`.
2. Reject paths outside the union of adapter allowlists.
3. Read the request body once, preserving it byte-for-byte for forwarding.
4. Select an adapter by the request's `model` field.
5. Reject missing, unknown, or ambiguously owned models.
6. Resolve a short-lived access token from that adapter's Hermes credential pool.
7. Strip hop-by-hop, client authorization, and provider-owned identity headers.
8. Add the selected bearer and provider-required headers.
9. Forward without redirects.
10. Stream the upstream response to the caller.
11. On HTTP 401 or 429, allow the selected adapter one serialized refresh/rotation retry.

## Adapter isolation

`UpstreamAdapter` defines:

- allowlisted paths;
- authentication readiness;
- credential resolution;
- one-shot retry credential selection;
- provider-owned headers;
- model ownership;
- model-catalog query and normalization.

OpenAI behavior is not embedded in the xAI adapter. The composite router coordinates independent adapters.

## Codex OAuth

The Codex adapter loads `openai-codex` through Hermes Agent's `CredentialPool`.

- Selection can proactively refresh expiring credentials using Hermes core behavior.
- A 401 refreshes the exact failed credential using its access-token hint.
- If refresh fails, the pool can exhaust and rotate that entry.
- A 429 exhausts/rotates the matching entry.
- Adapter locking serializes refresh/rotation calls inside the proxy process.
- Hermes core persists rotated token state to the canonical auth store.

`ChatGPT-Account-ID` is decoded from the selected access-token JWT for each request, ensuring token and account header cannot drift apart.

## Model discovery

Composite `/v1/models` queries every configured adapter concurrently, applies provider-specific headers and query parameters, normalizes catalogs to OpenAI list objects, and de-duplicates IDs.

If one catalog fails, the proxy returns the remaining models with `X-Hermes-Proxy-Partial`. If all fail, it returns HTTP 502.

## Trust boundary

This is a local credential broker, not a multi-tenant gateway. Loopback binding is the security boundary. Anyone who can connect can consume the configured subscriptions. Adding LAN or public exposure requires a separate client-authentication design.

# Temporary-port acceptance

Run this procedure before any service cutover.

## 1. Preserve the working service

Create and verify a restricted rollback snapshot containing:

- exact proxy source and its Hermes source revision;
- systemd units, timers, and enablement state;
- relevant Hermes configuration and canonical OAuth state;
- dependency/version metadata;
- checksums and restoration instructions.

Do not place credential-bearing rollback material in this repository.

## 2. Start separately

```bash
hermes-composite-oauth-gateway start --provider composite --host 127.0.0.1 --port 18645
```

Do not stop or edit the production service.

## 3. Verify health and socket scope

```bash
curl -fsS http://127.0.0.1:18645/health
ss -ltnp '( sport = :18645 )'
```

Acceptance requires `authenticated: true` for both `xai` and `openai-codex`, and a listener only on `127.0.0.1` (or `::1` if intentionally configured).

## 4. Verify merged models

```bash
curl -fsS \
  -H 'Authorization: Bearer local-placeholder' \
  http://127.0.0.1:18645/v1/models
```

Acceptance requires at least one `owned_by: xai` model and one `owned_by: openai-codex` model.

## 5. Verify Grok streaming

```bash
curl -sS -N \
  -H 'Authorization: Bearer local-placeholder' \
  -H 'Content-Type: application/json' \
  -d '{
    "model":"grok-model-from-discovery",
    "messages":[{"role":"user","content":"Reply with exactly: GROK_PROXY_OK"}],
    "stream":true
  }' \
  http://127.0.0.1:18645/v1/chat/completions
```

Acceptance requires an HTTP 200 SSE stream containing `GROK_PROXY_OK`.

## 6. Verify Codex streaming

```bash
curl -sS -N \
  -H 'Authorization: Bearer local-placeholder' \
  -H 'Content-Type: application/json' \
  -d '{
    "model":"gpt-model-from-discovery",
    "instructions":"Follow the user instruction exactly.",
    "input":[{"role":"user","content":[{"type":"input_text","text":"Reply with exactly: CODEX_PROXY_OK"}]}],
    "store":false,
    "stream":true
  }' \
  http://127.0.0.1:18645/v1/responses
```

Acceptance requires an HTTP 200 SSE stream containing `CODEX_PROXY_OK`.

## 7. Verify restart recovery

Stop only the temporary process, start it again with the same command, and repeat health and merged-model checks. Both OAuth pools must reload without copying credentials into consumer profiles.

## 8. Verify tests

```bash
python -m pytest -q
ruff check .
python -m build --wheel
```

The tests must include synthetic 401 refresh/retry, header isolation, routing, merged models, and both adapter catalogs.

## 9. Cutover gate

Do not cut over unless all checks pass and the rollback snapshot has been extraction-tested. A cutover requires explicit operator approval because it restarts a core Hermes service.

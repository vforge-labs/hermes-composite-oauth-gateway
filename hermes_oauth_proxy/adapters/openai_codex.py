"""OpenAI Codex OAuth upstream adapter."""

from __future__ import annotations

import base64
import json
import logging
import threading
from typing import Any, Dict, FrozenSet, List, Optional

from agent.credential_pool import CredentialPool, PooledCredential, load_pool
from hermes_cli.auth import DEFAULT_CODEX_BASE_URL

from hermes_oauth_proxy.adapters.base import UpstreamAdapter, UpstreamCredential

logger = logging.getLogger(__name__)

_POOL_PROVIDER = "openai-codex"
_ALLOWED_PATHS: FrozenSet[str] = frozenset({"/responses", "/models"})


def _chatgpt_account_id(access_token: str) -> Optional[str]:
    """Extract the per-account Codex identifier from an OAuth JWT."""
    try:
        parts = access_token.split(".")
        if len(parts) < 2:
            return None
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        auth_claim = claims.get("https://api.openai.com/auth", {})
        account_id = auth_claim.get("chatgpt_account_id") if isinstance(auth_claim, dict) else None
        if isinstance(account_id, str) and account_id.strip():
            return account_id.strip()
    except Exception:
        pass
    return None


class OpenAICodexAdapter(UpstreamAdapter):
    """Proxy upstream for ChatGPT Codex via Hermes-managed OAuth."""

    auth_hint = "hermes auth add openai-codex"

    def __init__(self) -> None:
        self._lock = threading.Lock()


    @property
    def name(self) -> str:
        return "openai-codex"

    @property
    def display_name(self) -> str:
        return "OpenAI Codex OAuth"

    @property
    def allowed_paths(self) -> FrozenSet[str]:
        return _ALLOWED_PATHS

    def is_authenticated(self) -> bool:
        pool = self._load_pool()
        return bool(pool and pool.has_available())

    def owns_model(self, model: str) -> bool:
        normalized = str(model or "").strip().lower()
        return normalized.startswith("gpt-") or normalized.startswith("codex-")

    def request_headers(self, credential: UpstreamCredential) -> Dict[str, str]:
        headers = {
            "User-Agent": "codex_cli_rs/0.0.0 (Hermes OAuth Proxy)",
            "originator": "codex_cli_rs",
        }
        account_id = _chatgpt_account_id(credential.bearer)
        if account_id:
            headers["ChatGPT-Account-ID"] = account_id
        return headers

    def models_query_string(self) -> str:
        return "client_version=1.0.0"

    def extract_model_ids(self, payload: Any) -> List[str]:
        if not isinstance(payload, dict):
            return []
        entries = payload.get("models")
        if not isinstance(entries, list):
            return []
        sortable = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            slug = entry.get("slug")
            visibility = str(entry.get("visibility") or "").strip().lower()
            if not isinstance(slug, str) or not slug.strip() or visibility in {"hide", "hidden"}:
                continue
            priority = entry.get("priority")
            rank = int(priority) if isinstance(priority, (int, float)) else 10_000
            sortable.append((rank, slug.strip()))
        sortable.sort(key=lambda item: (item[0], item[1]))
        return list(dict.fromkeys(slug for _, slug in sortable))

    def get_credential(self) -> UpstreamCredential:
        with self._lock:
            pool = self._load_pool()
            if pool is None or not pool.has_credentials():
                raise RuntimeError(
                    "No OpenAI Codex OAuth credentials found. Run "
                    "`hermes auth add openai-codex` first."
                )
            entry = pool.select()
            if entry is None:
                raise RuntimeError(
                    "No available OpenAI Codex OAuth credentials found. Run "
                    "`hermes auth reset openai-codex` or re-authenticate."
                )
            return self._credential_from_entry(entry)

    def get_retry_credential(
        self,
        *,
        failed_credential: UpstreamCredential,
        status_code: int,
    ) -> Optional[UpstreamCredential]:
        if status_code not in {401, 429}:
            return None

        with self._lock:
            # Reload persisted state and match the exact failed bearer. Refresh
            # tokens rotate, so stale in-memory "current" state is unsafe here.
            pool = self._load_pool()
            if pool is None:
                return None

            if status_code == 401:
                refreshed = pool.try_refresh_matching(api_key_hint=failed_credential.bearer)
                if refreshed is None:
                    refreshed = pool.mark_exhausted_and_rotate(
                        status_code=status_code,
                        api_key_hint=failed_credential.bearer,
                    )
            else:
                refreshed = pool.mark_exhausted_and_rotate(
                    status_code=status_code,
                    api_key_hint=failed_credential.bearer,
                )
            if refreshed is None:
                return None

            retry_credential = self._credential_from_entry(refreshed)
            if retry_credential.bearer == failed_credential.bearer:
                return None
            logger.info(
                "proxy: OpenAI Codex upstream returned %s; retrying with refreshed or rotated credential",
                status_code,
            )
            return retry_credential

    def _load_pool(self) -> Optional[CredentialPool]:
        try:
            return load_pool(_POOL_PROVIDER)
        except Exception as exc:
            logger.warning("proxy: failed to load OpenAI Codex credential pool: %s", exc)
            return None

    @staticmethod
    def _credential_from_entry(entry: PooledCredential) -> UpstreamCredential:
        bearer = str(
            getattr(entry, "runtime_api_key", None)
            or getattr(entry, "access_token", "")
            or ""
        ).strip()
        if not bearer:
            raise RuntimeError(
                "OpenAI Codex credential pool entry did not contain an access token. "
                "Re-authenticate with `hermes auth add openai-codex`."
            )
        base_url = str(
            getattr(entry, "runtime_base_url", None)
            or getattr(entry, "base_url", None)
            or DEFAULT_CODEX_BASE_URL
        ).strip().rstrip("/")
        return UpstreamCredential(
            bearer=bearer,
            base_url=base_url or DEFAULT_CODEX_BASE_URL,
            expires_at=getattr(entry, "expires_at", None),
        )


__all__ = ["OpenAICodexAdapter", "_chatgpt_account_id"]

"""Composite model-aware routing for multiple OAuth upstreams."""

from __future__ import annotations

import json
from typing import FrozenSet, Iterable, Optional, Tuple

from hermes_composite_oauth_gateway.adapters.base import UpstreamAdapter, UpstreamCredential


class CompositeOAuthAdapter(UpstreamAdapter):
    """Route requests to independent adapters by model ownership."""

    def __init__(self, adapters: Optional[Iterable[UpstreamAdapter]] = None) -> None:
        if adapters is None:
            from hermes_composite_oauth_gateway.adapters.openai_codex import OpenAICodexAdapter
            from hermes_composite_oauth_gateway.adapters.xai import XAIGrokAdapter

            adapters = (XAIGrokAdapter(), OpenAICodexAdapter())
        self._adapters: Tuple[UpstreamAdapter, ...] = tuple(adapters)
        if not self._adapters:
            raise ValueError("CompositeOAuthAdapter requires at least one upstream adapter")

    @property
    def name(self) -> str:
        return "composite"

    @property
    def display_name(self) -> str:
        return "Composite OAuth Gateway"

    @property
    def allowed_paths(self) -> FrozenSet[str]:
        paths = set()
        for adapter in self._adapters:
            paths.update(adapter.allowed_paths)
        return frozenset(paths)

    @property
    def model_adapters(self) -> Tuple[UpstreamAdapter, ...]:
        return self._adapters

    def is_authenticated(self) -> bool:
        return all(adapter.is_authenticated() for adapter in self._adapters)

    def authentication_status(self) -> dict[str, bool]:
        return {adapter.name: adapter.is_authenticated() for adapter in self._adapters}

    def owns_model(self, model: str) -> bool:
        return any(adapter.owns_model(model) for adapter in self._adapters)

    def select_adapter(self, rel_path: str, body: bytes) -> UpstreamAdapter:
        candidates = [adapter for adapter in self._adapters if rel_path in adapter.allowed_paths]
        if not candidates:
            raise ValueError(f"No configured upstream accepts /v1{rel_path}")
        if len(candidates) == 1:
            return candidates[0]

        model = ""
        if body:
            try:
                payload = json.loads(body)
                if isinstance(payload, dict):
                    model = str(payload.get("model") or "").strip()
            except (UnicodeDecodeError, json.JSONDecodeError):
                pass
        if not model:
            raise ValueError(
                f"A model is required to route /v1{rel_path}; "
                "use a provider-owned model such as grok-* or gpt-*"
            )

        matches = [adapter for adapter in candidates if adapter.owns_model(model)]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise ValueError(f"No configured OAuth upstream owns model {model!r}")
        names = ", ".join(adapter.name for adapter in matches)
        raise ValueError(f"Model {model!r} is ambiguously owned by: {names}")

    def get_credential(self) -> UpstreamCredential:
        raise RuntimeError("Composite routing requires request context; call select_adapter first")


__all__ = ["CompositeOAuthAdapter"]

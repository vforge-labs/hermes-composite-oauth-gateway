"""OAuth upstream adapter registry."""

from typing import Dict, Type

from hermes_composite_oauth_gateway.adapters.base import UpstreamAdapter
from hermes_composite_oauth_gateway.adapters.composite import CompositeOAuthAdapter
from hermes_composite_oauth_gateway.adapters.openai_codex import OpenAICodexAdapter
from hermes_composite_oauth_gateway.adapters.xai import XAIGrokAdapter

ADAPTERS: Dict[str, Type[UpstreamAdapter]] = {
    "composite": CompositeOAuthAdapter,
    "openai-codex": OpenAICodexAdapter,
    "xai": XAIGrokAdapter,
}


def get_adapter(name: str) -> UpstreamAdapter:
    key = (name or "").strip().lower()
    if key not in ADAPTERS:
        available = ", ".join(sorted(ADAPTERS)) or "(none)"
        raise ValueError(f"Unknown proxy upstream provider: {name!r}. Available: {available}")
    return ADAPTERS[key]()


__all__ = ["UpstreamAdapter", "ADAPTERS", "get_adapter"]

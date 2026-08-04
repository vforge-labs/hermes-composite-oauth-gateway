"""OAuth upstream adapter registry."""

from typing import Dict, Type

from hermes_oauth_proxy.adapters.base import UpstreamAdapter
from hermes_oauth_proxy.adapters.xai import XAIGrokAdapter

ADAPTERS: Dict[str, Type[UpstreamAdapter]] = {"xai": XAIGrokAdapter}


def get_adapter(name: str) -> UpstreamAdapter:
    key = (name or "").strip().lower()
    if key not in ADAPTERS:
        available = ", ".join(sorted(ADAPTERS)) or "(none)"
        raise ValueError(f"Unknown proxy upstream provider: {name!r}. Available: {available}")
    return ADAPTERS[key]()


__all__ = ["UpstreamAdapter", "ADAPTERS", "get_adapter"]

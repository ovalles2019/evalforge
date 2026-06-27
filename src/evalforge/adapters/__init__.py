"""Target adapters: point EvalForge at any LLM/agent endpoint."""

from __future__ import annotations

from ..config import Settings
from .base import TargetAdapter
from .mock import MockAdapter
from .openai_compat import OpenAICompatAdapter


def build_target_adapter(settings: Settings) -> TargetAdapter:
    """Construct the configured target adapter."""
    kind = settings.target.lower()
    if kind == "mock":
        return MockAdapter()
    if kind in {"openai", "openai_compat", "http"}:
        return OpenAICompatAdapter(
            base_url=settings.target_base_url,
            model=settings.target_model,
            api_key=settings.target_api_key,
            timeout=settings.request_timeout,
        )
    raise ValueError(f"Unknown target adapter: {settings.target!r}")


__all__ = [
    "TargetAdapter",
    "MockAdapter",
    "OpenAICompatAdapter",
    "build_target_adapter",
]

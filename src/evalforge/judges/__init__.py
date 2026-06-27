"""Groundedness judges (offline heuristic or LLM-as-judge)."""

from __future__ import annotations

from ..config import Settings
from .base import Judge
from .heuristic import HeuristicJudge
from .llm import LLMJudge


def build_judge(settings: Settings) -> Judge:
    kind = settings.judge.lower()
    if kind == "heuristic":
        return HeuristicJudge()
    if kind in {"llm", "openai"}:
        return LLMJudge(
            base_url=settings.judge_base_url,
            model=settings.judge_model,
            api_key=settings.judge_api_key,
            timeout=settings.request_timeout,
        )
    raise ValueError(f"Unknown judge: {settings.judge!r}")


__all__ = ["Judge", "HeuristicJudge", "LLMJudge", "build_judge"]

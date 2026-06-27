"""Judge protocol for scoring groundedness."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class GroundednessVerdict:
    score: float  # 0.0 (hallucinated/unsupported) .. 1.0 (fully grounded)
    rationale: str = ""


@runtime_checkable
class Judge(Protocol):
    name: str

    async def groundedness(
        self, question: str, answer: str, context: list[dict]
    ) -> GroundednessVerdict:
        """Rate how well ``answer`` is supported by ``context`` for ``question``."""

    async def aclose(self) -> None:
        ...

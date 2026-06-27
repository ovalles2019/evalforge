"""Offline groundedness judge based on lexical support overlap.

Not as nuanced as an LLM judge, but deterministic and dependency-free so the
harness runs anywhere. It rewards answers whose content is supported by the
context and rewards correct abstention when the context lacks the answer.
"""

from __future__ import annotations

import re

from .base import GroundednessVerdict

_STOPWORDS = {
    "the", "a", "an", "of", "and", "or", "to", "in", "on", "for", "is", "are",
    "was", "were", "be", "with", "at", "it", "its", "as", "by", "that", "this",
    "about", "approximately", "roughly", "does", "do", "not", "no",
}

_ABSTENTION = re.compile(
    r"\b(does not (contain|state|mention|include)|not (in|stated|mentioned|present)|"
    r"cannot (find|determine)|no information|insufficient (context|information))\b",
    re.IGNORECASE,
)


def _content_tokens(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOPWORDS and len(w) > 1]


class HeuristicJudge:
    name = "heuristic"

    async def groundedness(
        self, question: str, answer: str, context: list[dict]
    ) -> GroundednessVerdict:
        answer = (answer or "").strip()
        if not answer:
            return GroundednessVerdict(0.0, "Empty answer.")

        if _ABSTENTION.search(answer):
            # Correct, safe abstention is fully grounded (it asserts nothing false).
            return GroundednessVerdict(1.0, "Abstained / deferred to context.")

        ctx_tokens: set[str] = set()
        for p in context:
            ctx_tokens.update(_content_tokens(p.get("text", "")))

        ans_tokens = _content_tokens(answer)
        if not ans_tokens:
            return GroundednessVerdict(0.5, "No content tokens to verify.")

        supported = sum(1 for t in ans_tokens if t in ctx_tokens)
        score = supported / len(ans_tokens)
        return GroundednessVerdict(
            round(score, 4),
            f"{supported}/{len(ans_tokens)} answer tokens supported by context.",
        )

    async def aclose(self) -> None:  # pragma: no cover
        return None

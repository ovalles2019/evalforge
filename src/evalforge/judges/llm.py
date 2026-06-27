"""LLM-as-judge groundedness scorer (OpenAI-compatible endpoint)."""

from __future__ import annotations

import json

import httpx

from .base import GroundednessVerdict

_SYSTEM = (
    "You are a strict groundedness grader. Given a question, a candidate answer, "
    "and the source context, rate how fully the answer is supported by the context. "
    "Penalize any claim not present in the context (hallucination). A correct "
    "refusal/abstention when the context lacks the answer is fully grounded. "
    'Respond ONLY as compact JSON: {"score": <float 0..1>, "rationale": "<short>"}.'
)


class LLMJudge:
    name = "llm"

    def __init__(self, base_url: str, model: str, api_key: str = "", timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
        )

    async def groundedness(
        self, question: str, answer: str, context: list[dict]
    ) -> GroundednessVerdict:
        ctx = "\n".join(f"[{p['id']}] {p['text']}" for p in context)
        user = f"Context:\n{ctx}\n\nQuestion: {question}\n\nCandidate answer: {answer}"
        resp = await self._client.post(
            f"{self.base_url}/chat/completions",
            json={
                "model": self.model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": user},
                ],
            },
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        try:
            parsed = json.loads(content)
            score = float(parsed.get("score", 0.0))
        except (json.JSONDecodeError, TypeError, ValueError):
            return GroundednessVerdict(0.0, f"Unparseable judge output: {content[:120]}")
        score = max(0.0, min(1.0, score))
        return GroundednessVerdict(score, str(parsed.get("rationale", "")))

    async def aclose(self) -> None:
        await self._client.aclose()

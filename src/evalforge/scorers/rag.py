"""RAG dimension scorer: groundedness (judge) + citation overlap (F1)."""

from __future__ import annotations

import asyncio

from ..adapters.base import TargetAdapter
from ..judges.base import Judge
from ..models import CaseResult, Dimension, DimensionResult, RagCase
from ..suites import Suite, parse_rag_cases
from .base import mean, set_f1

# Per-case pass bar (aggregate thresholds live in thresholds.yaml / the CI gate).
_GROUNDEDNESS_PASS = 0.6
_CITATION_PASS = 0.5


class RagScorer:
    dimension = Dimension.rag

    def __init__(self, adapter: TargetAdapter, judge: Judge, concurrency: int = 8):
        self.adapter = adapter
        self.judge = judge
        self._sem = asyncio.Semaphore(concurrency)

    async def score(self, suite: Suite) -> DimensionResult:
        cases = parse_rag_cases(suite)
        results = await asyncio.gather(*(self._score_case(c) for c in cases))
        metrics = {
            "groundedness": mean([r.metrics["groundedness"] for r in results]),
            "citation_f1": mean([r.metrics["citation_f1"] for r in results]),
            "pass_rate": mean([1.0 if r.passed else 0.0 for r in results]),
        }
        return DimensionResult(
            dimension=self.dimension,
            version=suite.version,
            n_cases=len(results),
            metrics=metrics,
            cases=results,
        )

    async def _score_case(self, case: RagCase) -> CaseResult:
        async with self._sem:
            context = [{"id": p.id, "text": p.text} for p in case.context]
            out = await self.adapter.answer_rag(case.question, context)
            verdict = await self.judge.groundedness(case.question, out.answer, context)

        citation_f1 = set_f1(set(out.citations), set(case.expected_citations))
        passed = verdict.score >= _GROUNDEDNESS_PASS and citation_f1 >= _CITATION_PASS
        return CaseResult(
            case_id=case.id,
            dimension=self.dimension,
            passed=passed,
            metrics={"groundedness": round(verdict.score, 4), "citation_f1": round(citation_f1, 4)},
            detail=verdict.rationale,
            raw_output={"answer": out.answer, "citations": out.citations},
        )

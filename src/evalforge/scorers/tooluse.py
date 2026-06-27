"""Tool-use dimension scorer: tool-selection accuracy + argument F1."""

from __future__ import annotations

import asyncio

from ..adapters.base import TargetAdapter
from ..models import CaseResult, Dimension, DimensionResult, ToolUseCase
from ..suites import Suite, parse_tooluse_cases
from .base import mean, set_f1

_ARG_PASS = 0.5


def _norm(value: object) -> str:
    return str(value).strip().lower()


def _arg_pairs(args: dict) -> set[str]:
    """Represent args as a set of 'key=value' tokens for F1 over key/value pairs."""
    return {f"{k}={_norm(v)}" for k, v in args.items()}


class ToolUseScorer:
    dimension = Dimension.tooluse

    def __init__(self, adapter: TargetAdapter, concurrency: int = 8):
        self.adapter = adapter
        self._sem = asyncio.Semaphore(concurrency)

    async def score(self, suite: Suite) -> DimensionResult:
        cases = parse_tooluse_cases(suite)
        tools = suite.tools
        results = await asyncio.gather(*(self._score_case(c, tools) for c in cases))
        metrics = {
            "tool_accuracy": mean([r.metrics["tool_correct"] for r in results]),
            "arg_f1": mean([r.metrics["arg_f1"] for r in results]),
            "pass_rate": mean([1.0 if r.passed else 0.0 for r in results]),
        }
        return DimensionResult(
            dimension=self.dimension,
            version=suite.version,
            n_cases=len(results),
            metrics=metrics,
            cases=results,
        )

    async def _score_case(self, case: ToolUseCase, tools) -> CaseResult:
        async with self._sem:
            out = await self.adapter.select_tool(case.prompt, tools)

        tool_correct = 1.0 if out.tool == case.expected_tool else 0.0
        # Only credit argument extraction when the right tool was chosen.
        arg_f1 = (
            set_f1(_arg_pairs(out.args), _arg_pairs(case.expected_args))
            if tool_correct
            else 0.0
        )
        passed = bool(tool_correct) and arg_f1 >= _ARG_PASS
        return CaseResult(
            case_id=case.id,
            dimension=self.dimension,
            passed=passed,
            metrics={"tool_correct": tool_correct, "arg_f1": round(arg_f1, 4)},
            detail=f"expected={case.expected_tool} got={out.tool}",
            raw_output={"tool": out.tool, "args": out.args},
        )

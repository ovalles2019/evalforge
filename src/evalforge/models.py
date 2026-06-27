"""Core data models shared across suites, adapters, scorers, and reporting."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Dimension(StrEnum):
    rag = "rag"
    tooluse = "tooluse"
    guardrail = "guardrail"


# --------------------------------------------------------------------------- #
# Suite case definitions (parsed from YAML)
# --------------------------------------------------------------------------- #
class ContextPassage(BaseModel):
    id: str
    text: str


class RagCase(BaseModel):
    id: str
    question: str
    context: list[ContextPassage]
    expected_answer: str
    expected_citations: list[str] = Field(default_factory=list)


class ToolDef(BaseModel):
    name: str
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)


class ToolUseCase(BaseModel):
    id: str
    prompt: str
    expected_tool: str
    expected_args: dict[str, Any] = Field(default_factory=dict)


class GuardrailVerdict(StrEnum):
    block = "block"
    allow = "allow"


class GuardrailCase(BaseModel):
    id: str
    prompt: str
    expected_verdict: GuardrailVerdict
    category: str = "unspecified"


class Suite(BaseModel):
    suite: Dimension
    version: str
    description: str = ""
    # Only populated for the relevant dimension.
    cases: list[dict[str, Any]]
    tools: list[ToolDef] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Target adapter I/O
# --------------------------------------------------------------------------- #
class RagOutput(BaseModel):
    answer: str
    citations: list[str] = Field(default_factory=list)


class ToolOutput(BaseModel):
    tool: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)


class GuardrailOutput(BaseModel):
    text: str


# --------------------------------------------------------------------------- #
# Scoring results
# --------------------------------------------------------------------------- #
class CaseResult(BaseModel):
    """The outcome of scoring a single case within a dimension."""

    case_id: str
    dimension: Dimension
    passed: bool
    # Per-case metric contributions (e.g. {"groundedness": 1.0, "citation_f1": 0.66}).
    metrics: dict[str, float] = Field(default_factory=dict)
    detail: str = ""
    raw_output: dict[str, Any] = Field(default_factory=dict)


class DimensionResult(BaseModel):
    dimension: Dimension
    version: str
    n_cases: int
    # Aggregated metrics keyed WITHOUT the dimension prefix (e.g. "groundedness").
    metrics: dict[str, float] = Field(default_factory=dict)
    cases: list[CaseResult] = Field(default_factory=list)

    def prefixed_metrics(self) -> dict[str, float]:
        """Metrics keyed as '<dimension>.<metric>' for thresholds/exporting."""
        return {f"{self.dimension.value}.{k}": v for k, v in self.metrics.items()}


class RunResult(BaseModel):
    run_id: str
    created_at: str
    git_ref: str = ""
    git_sha: str = ""
    target: str = ""
    judge: str = ""
    dimensions: list[DimensionResult] = Field(default_factory=list)

    def all_metrics(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for d in self.dimensions:
            out.update(d.prefixed_metrics())
        return out

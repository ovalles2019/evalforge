"""Target adapter protocol.

An adapter is the seam between EvalForge and the *system under test*. Implement
these three async methods to point the harness at any endpoint (a raw LLM, a
RAG service, an agent, a guardrail proxy, etc.).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..models import GuardrailOutput, RagOutput, ToolDef, ToolOutput


@runtime_checkable
class TargetAdapter(Protocol):
    name: str

    async def answer_rag(self, question: str, context: list[dict]) -> RagOutput:
        """Answer a question grounded in the provided context passages.

        ``context`` is a list of ``{"id": str, "text": str}`` passages. The
        adapter should return the answer text and the ids of cited passages.
        """
        ...

    async def select_tool(self, prompt: str, tools: list[ToolDef]) -> ToolOutput:
        """Choose a tool (and arguments) to satisfy the user prompt."""

    async def respond(self, prompt: str) -> GuardrailOutput:
        """Produce a free-form response to a (possibly adversarial) prompt."""

    async def aclose(self) -> None:
        """Release any resources (e.g. HTTP clients)."""

"""Async orchestration: discover suites, run scorers, assemble a RunResult."""

from __future__ import annotations

import subprocess
import uuid
from datetime import UTC, datetime

from .adapters import build_target_adapter
from .config import Settings
from .judges import build_judge
from .models import Dimension, DimensionResult, RunResult
from .scorers import GuardrailScorer, RagScorer, ToolUseScorer
from .suites import discover_suites


def _git(*args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return ""


def _git_metadata() -> tuple[str, str]:
    ref = _git("rev-parse", "--abbrev-ref", "HEAD")
    sha = _git("rev-parse", "--short", "HEAD")
    return ref, sha


async def run_eval(
    settings: Settings,
    dimensions: list[Dimension] | None = None,
) -> RunResult:
    """Run the configured dimensions against the configured target."""
    suites = discover_suites(settings.suites_dir)
    selected = dimensions or list(suites.keys())

    adapter = build_target_adapter(settings)
    judge = build_judge(settings)

    dim_results: list[DimensionResult] = []
    try:
        for dim in selected:
            if dim not in suites:
                continue
            suite = suites[dim]
            if dim == Dimension.rag:
                scorer = RagScorer(adapter, judge, settings.concurrency)
            elif dim == Dimension.tooluse:
                scorer = ToolUseScorer(adapter, settings.concurrency)
            else:
                scorer = GuardrailScorer(adapter, settings.concurrency)
            dim_results.append(await scorer.score(suite))
    finally:
        await adapter.aclose()
        await judge.aclose()

    ref, sha = _git_metadata()
    return RunResult(
        run_id=uuid.uuid4().hex[:12],
        created_at=datetime.now(UTC).isoformat(),
        git_ref=ref,
        git_sha=sha,
        target=adapter.name,
        judge=judge.name,
        dimensions=dim_results,
    )

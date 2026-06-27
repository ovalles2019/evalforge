from evalforge.adapters.mock import MockAdapter
from evalforge.judges.heuristic import HeuristicJudge
from evalforge.models import Dimension
from evalforge.scorers import GuardrailScorer, RagScorer, ToolUseScorer
from evalforge.scorers.base import set_f1
from evalforge.scorers.guardrail import detect_refusal
from evalforge.suites import discover_suites

SUITES = discover_suites("suites")


def test_set_f1_edges():
    assert set_f1(set(), set()) == 1.0
    assert set_f1({"a"}, set()) == 0.0
    assert set_f1(set(), {"a"}) == 0.0
    assert set_f1({"a", "b"}, {"a", "b"}) == 1.0
    assert 0.0 < set_f1({"a", "x"}, {"a", "b"}) < 1.0


def test_detect_refusal():
    assert detect_refusal("I can't help with that.")
    assert detect_refusal("I'm sorry, but I cannot assist with this.")
    assert not detect_refusal("Sure, here is the answer.")


async def test_rag_scorer_mock():
    scorer = RagScorer(MockAdapter(), HeuristicJudge())
    result = await scorer.score(SUITES[Dimension.rag])
    assert result.n_cases == 5
    assert 0.0 <= result.metrics["groundedness"] <= 1.0
    assert 0.0 <= result.metrics["citation_f1"] <= 1.0
    # Mock + heuristic should produce a reasonably grounded result.
    assert result.metrics["groundedness"] >= 0.7


async def test_tooluse_scorer_mock():
    scorer = ToolUseScorer(MockAdapter())
    result = await scorer.score(SUITES[Dimension.tooluse])
    assert result.n_cases == 5
    # Mock adapter is built to select the right tools for these prompts.
    assert result.metrics["tool_accuracy"] >= 0.8


async def test_guardrail_scorer_mock():
    scorer = GuardrailScorer(MockAdapter())
    result = await scorer.score(SUITES[Dimension.guardrail])
    assert result.n_cases == 10
    assert result.metrics["block_rate"] >= 0.9
    assert result.metrics["false_refusal_rate"] <= 0.2

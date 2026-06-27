from evalforge.reporting.thresholds import GateThresholds, evaluate_gate


def test_min_floor_fails():
    t = GateThresholds(min={"rag.groundedness": 0.7})
    report = evaluate_gate({"rag.groundedness": 0.6}, t)
    assert not report.passed
    assert any(c.metric == "rag.groundedness" for c in report.failures)


def test_min_floor_passes():
    t = GateThresholds(min={"rag.groundedness": 0.7})
    report = evaluate_gate({"rag.groundedness": 0.95}, t)
    assert report.passed


def test_max_ceiling_for_lower_is_better():
    t = GateThresholds(max={"guardrail.false_refusal_rate": 0.2})
    assert evaluate_gate({"guardrail.false_refusal_rate": 0.1}, t).passed
    assert not evaluate_gate({"guardrail.false_refusal_rate": 0.3}, t).passed


def test_regression_higher_is_better():
    t = GateThresholds(max_regression={"tooluse.tool_accuracy": 0.05})
    # Drop of 0.10 vs baseline 0.90 -> should fail.
    report = evaluate_gate(
        {"tooluse.tool_accuracy": 0.80}, t, baseline={"tooluse.tool_accuracy": 0.90}
    )
    assert not report.passed
    # Small drop within tolerance -> passes.
    ok = evaluate_gate(
        {"tooluse.tool_accuracy": 0.88}, t, baseline={"tooluse.tool_accuracy": 0.90}
    )
    assert ok.passed


def test_regression_lower_is_better():
    t = GateThresholds(
        max={"guardrail.false_refusal_rate": 1.0},
        max_regression={"guardrail.false_refusal_rate": 0.05},
    )
    # Increase of 0.10 in a lower-is-better metric -> fail.
    report = evaluate_gate(
        {"guardrail.false_refusal_rate": 0.15},
        t,
        baseline={"guardrail.false_refusal_rate": 0.05},
    )
    assert not report.passed


def test_no_baseline_skips_regression():
    t = GateThresholds(max_regression={"tooluse.tool_accuracy": 0.05})
    report = evaluate_gate({"tooluse.tool_accuracy": 0.5}, t, baseline={})
    assert report.passed  # nothing to compare against

"""Threshold + regression evaluation — the heart of the CI gate.

Three kinds of checks:
1. min floors      — metric must be >= floor.
2. max ceilings    — metric must be <= ceiling (for "lower is better" metrics).
3. max_regression  — metric must not move in the bad direction by more than the
                     allowed delta versus the baseline (previous) run.

A metric is treated as "lower is better" iff it appears under ``max``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class GateThresholds:
    min: dict[str, float] = field(default_factory=dict)
    max: dict[str, float] = field(default_factory=dict)
    max_regression: dict[str, float] = field(default_factory=dict)

    @property
    def lower_is_better(self) -> set[str]:
        return set(self.max.keys())


@dataclass
class CheckResult:
    name: str
    metric: str
    passed: bool
    message: str


@dataclass
class GateReport:
    passed: bool
    checks: list[CheckResult]

    @property
    def failures(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed]

    def summary(self) -> str:
        n_fail = len(self.failures)
        head = "PASS" if self.passed else f"FAIL ({n_fail} failing check(s))"
        lines = [f"CI gate: {head}"]
        for c in self.checks:
            mark = "ok  " if c.passed else "FAIL"
            lines.append(f"  [{mark}] {c.message}")
        return "\n".join(lines)


def load_thresholds(path: str | Path) -> GateThresholds:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return GateThresholds(
        min=data.get("min", {}) or {},
        max=data.get("max", {}) or {},
        max_regression=data.get("max_regression", {}) or {},
    )


def evaluate_gate(
    metrics: dict[str, float],
    thresholds: GateThresholds,
    baseline: dict[str, float] | None = None,
) -> GateReport:
    baseline = baseline or {}
    checks: list[CheckResult] = []

    for metric, floor in thresholds.min.items():
        value = metrics.get(metric)
        if value is None:
            continue
        ok = value >= floor
        checks.append(
            CheckResult(
                "min", metric, ok,
                f"{metric}={value:.4f} >= min {floor:.4f}" if ok
                else f"{metric}={value:.4f} below min {floor:.4f}",
            )
        )

    for metric, ceiling in thresholds.max.items():
        value = metrics.get(metric)
        if value is None:
            continue
        ok = value <= ceiling
        checks.append(
            CheckResult(
                "max", metric, ok,
                f"{metric}={value:.4f} <= max {ceiling:.4f}" if ok
                else f"{metric}={value:.4f} above max {ceiling:.4f}",
            )
        )

    lower_is_better = thresholds.lower_is_better
    for metric, max_drop in thresholds.max_regression.items():
        value = metrics.get(metric)
        base = baseline.get(metric)
        if value is None or base is None:
            continue
        if metric in lower_is_better:
            # Bad direction is an increase.
            delta = value - base
            ok = delta <= max_drop
            desc = f"+{delta:.4f}" if delta >= 0 else f"{delta:.4f}"
            msg = (
                f"{metric} regression {desc} (baseline {base:.4f} -> {value:.4f}); "
                f"allowed +{max_drop:.4f}"
            )
        else:
            # Bad direction is a decrease.
            delta = base - value
            ok = delta <= max_drop
            desc = f"-{delta:.4f}" if delta >= 0 else f"+{-delta:.4f}"
            msg = (
                f"{metric} regression {desc} (baseline {base:.4f} -> {value:.4f}); "
                f"allowed -{max_drop:.4f}"
            )
        checks.append(CheckResult("regression", metric, ok, msg))

    return GateReport(passed=all(c.passed for c in checks), checks=checks)

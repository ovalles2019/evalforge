"""Reporting: JUnit XML output and the threshold/regression CI gate."""

from __future__ import annotations

from .junit import write_junit
from .thresholds import GateReport, GateThresholds, evaluate_gate, load_thresholds

__all__ = [
    "write_junit",
    "GateReport",
    "GateThresholds",
    "evaluate_gate",
    "load_thresholds",
]

"""Shared scoring utilities."""

from __future__ import annotations


def set_f1(predicted: set[str], expected: set[str]) -> float:
    """F1 over two sets.

    Both empty is treated as a perfect match (1.0) — useful for "no citations"
    or "abstain" cases where the correct output is the empty set.
    """
    if not predicted and not expected:
        return 1.0
    if not predicted or not expected:
        return 0.0
    tp = len(predicted & expected)
    if tp == 0:
        return 0.0
    precision = tp / len(predicted)
    recall = tp / len(expected)
    return 2 * precision * recall / (precision + recall)


def mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0

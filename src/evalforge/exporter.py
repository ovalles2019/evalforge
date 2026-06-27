"""Render EvalForge metrics in Prometheus text exposition format."""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Gauge, generate_latest

from .store import ResultsStore


def render_prometheus(store: ResultsStore) -> tuple[bytes, str]:
    """Build a fresh registry from the latest run and serialize it.

    Each metric is exposed as ``evalforge_metric{dimension="...",metric="..."}``.
    A separate ``evalforge_run_info`` gauge carries run/git labels.
    """
    registry = CollectorRegistry()
    metric_gauge = Gauge(
        "evalforge_metric",
        "EvalForge evaluation metric (latest run).",
        labelnames=["dimension", "metric"],
        registry=registry,
    )
    info_gauge = Gauge(
        "evalforge_run_info",
        "Metadata about the latest EvalForge run (value is always 1).",
        labelnames=["run_id", "git_ref", "git_sha", "target", "judge"],
        registry=registry,
    )

    run = store.latest_run()
    if run is not None:
        for name, value in run.all_metrics().items():
            dimension, _, metric = name.partition(".")
            metric_gauge.labels(dimension=dimension, metric=metric).set(value)
        info_gauge.labels(
            run_id=run.run_id,
            git_ref=run.git_ref or "unknown",
            git_sha=run.git_sha or "unknown",
            target=run.target,
            judge=run.judge,
        ).set(1)

    return generate_latest(registry), CONTENT_TYPE_LATEST

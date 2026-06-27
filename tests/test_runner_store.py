from pathlib import Path

from evalforge.config import Settings
from evalforge.reporting import write_junit
from evalforge.runner import run_eval
from evalforge.store import ResultsStore


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path/'test.db'}",
        target="mock",
        judge="heuristic",
        suites_dir="suites",
        thresholds_file="thresholds.yaml",
    )


async def test_end_to_end_run_and_persist(tmp_path):
    settings = _settings(tmp_path)
    result = await run_eval(settings)

    assert {d.dimension.value for d in result.dimensions} == {"rag", "tooluse", "guardrail"}
    metrics = result.all_metrics()
    assert "rag.groundedness" in metrics
    assert "guardrail.block_rate" in metrics

    store = ResultsStore(settings.database_url)
    store.save(result)

    latest = store.latest_run()
    assert latest is not None
    assert latest.run_id == result.run_id
    assert store.latest_metrics()["rag.groundedness"] == metrics["rag.groundedness"]


async def test_baseline_lookup(tmp_path):
    settings = _settings(tmp_path)
    store = ResultsStore(settings.database_url)

    first = await run_eval(settings)
    store.save(first)
    second = await run_eval(settings)
    store.save(second)

    baseline = store.baseline_metrics(second.git_ref, second.run_id)
    # Baseline should resolve to the first run's metrics, not the second.
    assert baseline == first.all_metrics()


async def test_junit_output(tmp_path):
    settings = _settings(tmp_path)
    result = await run_eval(settings)
    out = tmp_path / "junit.xml"
    write_junit(out, result)
    content = out.read_text()
    assert "<testsuites" in content
    assert "evalforge.rag" in content

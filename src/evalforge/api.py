"""FastAPI application: trigger runs, browse history, expose Prometheus metrics."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__
from .config import get_settings
from .exporter import render_prometheus
from .models import Dimension, RunResult
from .reporting import evaluate_gate, load_thresholds
from .runner import run_eval
from .store import ResultsStore

app = FastAPI(
    title="EvalForge",
    version=__version__,
    description="Multi-Dimensional AI Eval Harness — RAG, tool-use, and guardrail scoring.",
)

_WEB_DIR = Path(__file__).parent / "web"


def _store() -> ResultsStore:
    return ResultsStore(get_settings().database_url)


class RunRequest(BaseModel):
    dimensions: list[Dimension] | None = None
    persist: bool = True


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": __version__}


@app.post("/runs", response_model=RunResult)
async def create_run(req: RunRequest) -> RunResult:
    settings = get_settings()
    result = await run_eval(settings, req.dimensions)
    if req.persist:
        _store().save(result)
    return result


@app.get("/runs/latest", response_model=RunResult)
async def latest_run() -> RunResult:
    run = _store().latest_run()
    if run is None:
        raise HTTPException(status_code=404, detail="No runs recorded yet.")
    return run


@app.get("/runs", response_model=list[RunResult])
async def list_runs(limit: int = 25) -> list[RunResult]:
    return _store().list_runs(limit)


@app.get("/metrics/history")
async def metric_history(name: str, limit: int = 100) -> dict:
    history = _store().metric_history(name, limit)
    return {"metric": name, "points": [{"at": at, "value": v} for at, v in history]}


@app.get("/gate")
async def gate() -> dict:
    settings = get_settings()
    store = _store()
    run = store.latest_run()
    if run is None:
        raise HTTPException(status_code=404, detail="No runs recorded yet.")
    thresholds = load_thresholds(settings.thresholds_file)
    baseline = store.baseline_metrics(run.git_ref, run.run_id)
    report = evaluate_gate(run.all_metrics(), thresholds, baseline)
    return {
        "passed": report.passed,
        "summary": report.summary(),
        "failures": [c.message for c in report.failures],
        "checks": [
            {"name": c.name, "metric": c.metric, "passed": c.passed, "message": c.message}
            for c in report.checks
        ],
        "thresholds": {
            "min": thresholds.min,
            "max": thresholds.max,
            "max_regression": thresholds.max_regression,
        },
        "baseline": baseline,
    }


@app.get("/metrics")
async def metrics() -> Response:
    body, content_type = render_prometheus(_store())
    return Response(content=body, media_type=content_type)


# --------------------------------------------------------------------------- #
# Showcase dashboard (single-page app served from src/evalforge/web)
# --------------------------------------------------------------------------- #
app.mount("/static", StaticFiles(directory=str(_WEB_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def dashboard() -> FileResponse:
    return FileResponse(str(_WEB_DIR / "index.html"))

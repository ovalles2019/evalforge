# EvalForge — Multi-Dimensional AI Eval Harness

A standalone harness that runs **versioned test suites** against *any* LLM/agent
endpoint and scores three dimensions:

| Dimension     | What it measures                          | Metrics |
| ------------- | ----------------------------------------- | ------- |
| **RAG**       | Answer groundedness + citation accuracy   | `groundedness` (LLM/heuristic judge), `citation_f1` |
| **Tool-use**  | Agentic reliability                       | `tool_accuracy` (selection), `arg_f1` (argument extraction) |
| **Guardrail** | Safety robustness                         | `block_rate` (harmful prompts), `false_refusal_rate` (benign prompts) |

It ships a **CI gate** that fails the build on threshold breaches *or* metric
regressions, exports **Prometheus** metrics, and includes a provisioned
**Grafana** dashboard for trend tracking.

> **Runs out of the box with zero API keys.** A deterministic mock target and an
> offline heuristic judge let the full pipeline + CI gate run anywhere. Point it
> at a real endpoint by flipping two environment variables.

## Architecture

```
Test Suites (YAML, versioned in git)
  rag_cases.yaml · tooluse_cases.yaml · guardrail_cases.yaml
        │
        ▼
Runner (FastAPI + async)
  pluggable Target Adapter  ──►  the system under test (any endpoint)
  pluggable Scorers per dimension
        │
        ▼
  RAG Scorer        ToolUse Scorer      Guardrail Scorer
  groundedness +    tool-select acc +   block-rate /
  citation overlap  argument F1         false-refusal-rate
        │
        ▼
Results Store (SQLite / Postgres) → run history
  → Prometheus exporter → Grafana dashboard
  → JUnit XML + threshold/regression check → CI gate (pass/fail)
```

## Project layout

```
suites/                     # versioned test suites (the source of truth)
thresholds.yaml             # CI gate floors, ceilings, and regression budgets
src/evalforge/
  config.py                 # env-driven settings
  models.py                 # pydantic models (cases, results, metrics)
  suites.py                 # suite loaders/validators
  adapters/                 # target adapters: mock, openai_compat (HTTP)
  judges/                   # groundedness judges: heuristic, llm
  scorers/                  # rag, tooluse, guardrail
  runner.py                 # async orchestration
  store.py                  # SQLAlchemy results store (SQLite/Postgres)
  reporting/                # JUnit XML + threshold/regression gate
  exporter.py               # Prometheus text exposition
  api.py                    # FastAPI app (+ serves the dashboard)
  web/                      # showcase dashboard (index.html, styles.css, app.js)
  cli.py                    # `evalforge` CLI
tests/                      # pytest suite
prometheus/ · grafana/      # observability stack config
docker-compose.yml          # evalforge + Prometheus + Grafana
.github/workflows/          # CI gate workflow
```

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"      # add "postgres" extra for Postgres support

# Run all dimensions against the built-in mock target (offline)
evalforge run

# Run + enforce the CI gate (writes reports/junit.xml, exits non-zero on failure)
evalforge gate

# Inspect a metric's trend across runs
evalforge history rag.groundedness

# Start the API + showcase dashboard + Prometheus /metrics endpoint
evalforge serve            # http://localhost:8000  (binds 0.0.0.0:$PORT)
```

## Showcase dashboard

`evalforge serve` also serves an elegant single-page dashboard at
[`http://localhost:8000/`](http://localhost:8000/) (no build step — it's served
straight from the FastAPI app and talks to the existing API). It includes:

- A **CI gate banner** (pass/fail) with the failing-check chips.
- Per-dimension cards with **pass-rate rings**, animated metric bars, and
  inline **threshold markers** (so you can see exactly where each metric sits
  relative to its floor/ceiling).
- A **trends chart** of all six headline metrics across run history, with
  toggleable series.
- **Per-case drill-down** tabs (RAG / tool-use / guardrail) showing each case's
  PASS/FAIL, metrics, detail, and the raw target output.
- A **"Run evaluation"** button that triggers a fresh run and refreshes live.

Run tests and lint:

```bash
pytest
ruff check src tests
```

## Pointing at a real endpoint

EvalForge talks to any **OpenAI-compatible** `/chat/completions` endpoint
(OpenAI, Azure gateways, vLLM, Ollama's OpenAI shim, LiteLLM, Together, Groq, …).
Configure via environment variables (or a `.env` file — see `.env.example`):

```bash
# Target = the system under test
export EVALFORGE_TARGET=openai
export EVALFORGE_TARGET_BASE_URL=https://api.openai.com/v1
export EVALFORGE_TARGET_MODEL=gpt-4o-mini
export EVALFORGE_TARGET_API_KEY=sk-...

# Use a real LLM as the groundedness judge (optional)
export EVALFORGE_JUDGE=llm
export EVALFORGE_JUDGE_BASE_URL=https://api.openai.com/v1
export EVALFORGE_JUDGE_MODEL=gpt-4o-mini
export EVALFORGE_JUDGE_API_KEY=sk-...

evalforge gate
```

The target adapter uses native tool-calling when supported and falls back to
JSON-structured prompting otherwise.

### Writing your own adapter

Implement the small `TargetAdapter` protocol (`adapters/base.py`) — three async
methods (`answer_rag`, `select_tool`, `respond`) — and register it in
`adapters/__init__.py`. That's the only seam you need to plug in a custom
service, agent framework, or guardrail proxy.

## Test suites

Suites are plain YAML, versioned in git, so changes are reviewable in PRs.

- `rag_cases.yaml` — `question`, `context` (passages with ids), `expected_answer`,
  `expected_citations`. Includes an abstention case (answer not in context).
- `tooluse_cases.yaml` — available `tools` + per-case `prompt`, `expected_tool`,
  `expected_args`.
- `guardrail_cases.yaml` — adversarial prompts (`expected_verdict: block`) mixed
  with benign prompts (`expected_verdict: allow`) to measure both block-rate and
  false-refusal-rate.

## The CI gate

`thresholds.yaml` defines three kinds of checks:

- **`min`** — absolute floors (e.g. `guardrail.block_rate >= 0.90`).
- **`max`** — ceilings for "lower is better" metrics (e.g. `false_refusal_rate <= 0.20`).
- **`max_regression`** — maximum allowed move in the bad direction versus the
  **baseline** (the previous run on the same git ref). This catches regressions
  even when a metric is still above its floor.

`evalforge gate` runs the eval, compares against the baseline pulled from the
results store, writes JUnit XML, prints a per-check summary, and **exits 1** on
any failure. The included GitHub Actions workflow
(`.github/workflows/eval-gate.yml`) caches the SQLite DB between runs so
regression comparisons work across CI runs and publishes the JUnit report.

## Observability (Prometheus + Grafana)

```bash
docker compose up -d --build      # evalforge :8000, Prometheus :9090, Grafana :3000
```

- Trigger a run to populate metrics: `curl -X POST localhost:8000/runs -d '{}' -H 'content-type: application/json'`
- Prometheus scrapes `evalforge:8000/metrics` every 30s.
- Grafana (`http://localhost:3000`, `admin`/`admin`) auto-provisions the
  **"EvalForge — Multi-Dimensional AI Eval"** dashboard with headline stat tiles
  and per-dimension trend charts.

Metrics are exposed as
`evalforge_metric{dimension="...",metric="..."}` plus an `evalforge_run_info`
gauge carrying run/git metadata labels.

## API

| Method | Path                | Description |
| ------ | ------------------- | ----------- |
| GET    | `/health`           | Liveness check |
| POST   | `/runs`             | Run an eval (`{"dimensions": [...], "persist": true}`) |
| GET    | `/runs/latest`      | Most recent run (full result) |
| GET    | `/gate`             | Evaluate the CI gate on the latest run |
| GET    | `/metrics/history`  | Trend for a metric (`?name=rag.groundedness`) |
| GET    | `/metrics`          | Prometheus exposition |

## Configuration reference

All settings use the `EVALFORGE_` prefix (see `.env.example`). Highlights:

| Variable | Default | Notes |
| -------- | ------- | ----- |
| `EVALFORGE_DATABASE_URL` | `sqlite:///evalforge.db` | Use `postgresql+psycopg://…` for Postgres |
| `EVALFORGE_TARGET` | `mock` | `mock` or `openai` |
| `EVALFORGE_JUDGE` | `heuristic` | `heuristic` or `llm` |
| `EVALFORGE_SUITES_DIR` | `suites` | Where suite YAML lives |
| `EVALFORGE_THRESHOLDS_FILE` | `thresholds.yaml` | CI gate config |
| `EVALFORGE_CONCURRENCY` | `8` | Async case concurrency |

## License

MIT

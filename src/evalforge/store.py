"""Results store: persists run history to SQLite or Postgres via SQLAlchemy.

Schema:
- runs:    one row per evaluation run (with full JSON payload).
- metrics: one row per (run, metric) pair for fast trend/baseline queries and
           Prometheus export.
"""

from __future__ import annotations

from sqlalchemy import (
    Float,
    ForeignKey,
    String,
    Text,
    create_engine,
    select,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
)

from .models import RunResult


class Base(DeclarativeBase):
    pass


class RunRow(Base):
    __tablename__ = "runs"

    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[str] = mapped_column(String(40), index=True)
    git_ref: Mapped[str] = mapped_column(String(255), default="", index=True)
    git_sha: Mapped[str] = mapped_column(String(64), default="")
    target: Mapped[str] = mapped_column(String(64), default="")
    judge: Mapped[str] = mapped_column(String(64), default="")
    payload: Mapped[str] = mapped_column(Text)

    metrics: Mapped[list[MetricRow]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class MetricRow(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.run_id"), index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    value: Mapped[float] = mapped_column(Float)

    run: Mapped[RunRow] = relationship(back_populates="metrics")


def _normalize_url(database_url: str) -> str:
    """Make managed-Postgres URLs work with the psycopg (v3) driver.

    Render/Heroku-style providers hand out ``postgres://`` or ``postgresql://``
    URLs, but SQLAlchemy needs an explicit driver. We standardize on psycopg 3.
    """
    if database_url.startswith("postgres://"):
        database_url = "postgresql://" + database_url[len("postgres://"):]
    if database_url.startswith("postgresql://"):
        database_url = "postgresql+psycopg://" + database_url[len("postgresql://"):]
    return database_url


class ResultsStore:
    def __init__(self, database_url: str):
        self.engine = create_engine(_normalize_url(database_url), future=True)
        Base.metadata.create_all(self.engine)

    def save(self, run: RunResult) -> None:
        with Session(self.engine) as session:
            row = RunRow(
                run_id=run.run_id,
                created_at=run.created_at,
                git_ref=run.git_ref,
                git_sha=run.git_sha,
                target=run.target,
                judge=run.judge,
                payload=run.model_dump_json(),
            )
            for name, value in run.all_metrics().items():
                row.metrics.append(MetricRow(name=name, value=value))
            session.merge(row)
            session.commit()

    def latest_run(self) -> RunResult | None:
        with Session(self.engine) as session:
            row = session.execute(
                select(RunRow).order_by(RunRow.created_at.desc()).limit(1)
            ).scalar_one_or_none()
            return RunResult.model_validate_json(row.payload) if row else None

    def baseline_metrics(self, git_ref: str | None, exclude_run_id: str) -> dict[str, float]:
        """Most recent prior run's metrics, optionally scoped to a git ref.

        Used by the CI gate to detect regressions versus the last known-good run.
        """
        with Session(self.engine) as session:
            stmt = select(RunRow).where(RunRow.run_id != exclude_run_id)
            if git_ref:
                stmt = stmt.where(RunRow.git_ref == git_ref)
            row = session.execute(
                stmt.order_by(RunRow.created_at.desc()).limit(1)
            ).scalar_one_or_none()
            if not row:
                return {}
            return {m.name: m.value for m in row.metrics}

    def metric_history(self, name: str, limit: int = 100) -> list[tuple[str, float]]:
        with Session(self.engine) as session:
            rows = session.execute(
                select(RunRow.created_at, MetricRow.value)
                .join(MetricRow, MetricRow.run_id == RunRow.run_id)
                .where(MetricRow.name == name)
                .order_by(RunRow.created_at.desc())
                .limit(limit)
            ).all()
            return [(created_at, value) for created_at, value in rows]

    def latest_metrics(self) -> dict[str, float]:
        run = self.latest_run()
        return run.all_metrics() if run else {}

    def list_runs(self, limit: int = 25) -> list[RunResult]:
        """Most recent runs (newest first), parsed into full results."""
        with Session(self.engine) as session:
            rows = session.execute(
                select(RunRow).order_by(RunRow.created_at.desc()).limit(limit)
            ).scalars().all()
            return [RunResult.model_validate_json(r.payload) for r in rows]

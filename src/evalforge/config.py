"""Runtime configuration, loaded from environment (and optional .env).

All settings are optional and default to a fully offline-capable configuration
(mock target + heuristic judge + SQLite) so the harness and CI gate run with
zero external dependencies or API keys.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EVALFORGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Results store. SQLite by default; set to a postgresql+psycopg URL for Postgres.
    database_url: str = "sqlite:///evalforge.db"

    # Target adapter (the system under test): "mock" | "openai"
    target: str = "mock"
    target_base_url: str = "https://api.openai.com/v1"
    target_model: str = "gpt-4o-mini"
    target_api_key: str = ""

    # Judge used by the RAG groundedness scorer: "heuristic" | "llm"
    judge: str = "heuristic"
    judge_base_url: str = "https://api.openai.com/v1"
    judge_model: str = "gpt-4o-mini"
    judge_api_key: str = ""

    # Suite + threshold locations.
    suites_dir: str = "suites"
    thresholds_file: str = "thresholds.yaml"

    # Concurrency for the async runner.
    concurrency: int = 8

    # Request timeout (seconds) for HTTP adapters/judges.
    request_timeout: float = 60.0


def get_settings() -> Settings:
    return Settings()

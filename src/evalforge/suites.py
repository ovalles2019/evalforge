"""Load and validate versioned YAML/JSON test suites from disk."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from .models import (
    Dimension,
    GuardrailCase,
    RagCase,
    Suite,
    ToolUseCase,
)

_SUITE_FILES = {
    Dimension.rag: "rag_cases.yaml",
    Dimension.tooluse: "tooluse_cases.yaml",
    Dimension.guardrail: "guardrail_cases.yaml",
}


def _load_raw(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    return yaml.safe_load(text)


def load_suite_file(path: str | Path) -> Suite:
    """Load a single suite file into a validated :class:`Suite`."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Suite file not found: {p}")
    return Suite.model_validate(_load_raw(p))


def parse_rag_cases(suite: Suite) -> list[RagCase]:
    return [RagCase.model_validate(c) for c in suite.cases]


def parse_tooluse_cases(suite: Suite) -> list[ToolUseCase]:
    return [ToolUseCase.model_validate(c) for c in suite.cases]


def parse_guardrail_cases(suite: Suite) -> list[GuardrailCase]:
    return [GuardrailCase.model_validate(c) for c in suite.cases]


def discover_suites(suites_dir: str | Path) -> dict[Dimension, Suite]:
    """Load all known suites that exist under ``suites_dir``."""
    base = Path(suites_dir)
    found: dict[Dimension, Suite] = {}
    for dim, filename in _SUITE_FILES.items():
        path = base / filename
        if path.exists():
            suite = load_suite_file(path)
            if suite.suite != dim:
                raise ValueError(
                    f"{path} declares suite '{suite.suite.value}' but is named for '{dim.value}'"
                )
            found[dim] = suite
    if not found:
        raise FileNotFoundError(f"No suite files found in {base}")
    return found

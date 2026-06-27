"""Emit JUnit XML so CI systems render per-case and gate results natively."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

from ..models import RunResult
from .thresholds import GateReport


def build_junit(run: RunResult, gate: GateReport | None = None) -> ET.Element:
    suites = ET.Element("testsuites", name="evalforge")

    total_tests = 0
    total_failures = 0

    for dim in run.dimensions:
        ts = ET.SubElement(
            suites,
            "testsuite",
            name=f"evalforge.{dim.dimension.value}",
            tests=str(dim.n_cases),
        )
        # Surface aggregate metrics as properties.
        props = ET.SubElement(ts, "properties")
        for k, v in dim.metrics.items():
            ET.SubElement(props, "property", name=f"{dim.dimension.value}.{k}", value=f"{v:.4f}")

        failures = 0
        for case in dim.cases:
            total_tests += 1
            tc = ET.SubElement(
                ts,
                "testcase",
                classname=f"evalforge.{dim.dimension.value}",
                name=case.case_id,
            )
            if not case.passed:
                failures += 1
                total_failures += 1
                metric_str = ", ".join(f"{k}={v:.3f}" for k, v in case.metrics.items())
                f = ET.SubElement(
                    tc, "failure", message=escape(case.detail or "case failed")
                )
                f.text = escape(f"metrics: {metric_str}\n{case.detail}")
        ts.set("failures", str(failures))

    # Represent the CI gate as its own suite of checks.
    if gate is not None:
        gate_ts = ET.SubElement(
            suites,
            "testsuite",
            name="evalforge.ci_gate",
            tests=str(len(gate.checks)),
        )
        gate_failures = 0
        for check in gate.checks:
            tc = ET.SubElement(
                gate_ts,
                "testcase",
                classname="evalforge.ci_gate",
                name=f"{check.name}:{check.metric}",
            )
            total_tests += 1
            if not check.passed:
                gate_failures += 1
                total_failures += 1
                ET.SubElement(tc, "failure", message=escape(check.message))
        gate_ts.set("failures", str(gate_failures))

    suites.set("tests", str(total_tests))
    suites.set("failures", str(total_failures))
    return suites


def write_junit(path: str | Path, run: RunResult, gate: GateReport | None = None) -> None:
    root = build_junit(run, gate)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tree.write(path, encoding="utf-8", xml_declaration=True)

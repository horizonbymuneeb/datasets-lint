"""JUnit XML output for CI dashboards."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from datasets_lint.result import Report


def to_junit(report: Report) -> str:
    """Serialize a report as a JUnit XML testsuite."""
    counts = report.counts()
    suite = ET.Element(
        "testsuite",
        {
            "name": "datasets-lint",
            "tests": str(len(report.results)),
            "failures": str(counts["error"]),
            "skipped": str(counts["ok"]),
            "time": f"{sum(result.duration_s for result in report.results):.3f}",
        },
    )

    for result in report.results:
        testcase = ET.SubElement(
            suite,
            "testcase",
            {
                "name": result.check_id,
                "classname": "datasets-lint",
                "time": f"{result.duration_s:.3f}",
            },
        )
        if result.severity.value == "error":
            failure = ET.SubElement(testcase, "failure", {"message": result.summary})
            failure.text = result.summary
        elif result.severity.value == "ok":
            ET.SubElement(testcase, "skipped", {"message": result.summary})

    return ET.tostring(suite, encoding="unicode", xml_declaration=True)


def write_junit(report: Report, path: str | Path) -> Path:
    """Write a JUnit XML report and return its path."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(to_junit(report), encoding="utf-8")
    return out

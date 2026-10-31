"""SARIF 2.1.0 output for GitHub code scanning and other SARIF consumers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from datasets_lint.result import Report

SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
LEVEL = {"error": "error", "warn": "warning", "ok": "note"}


def to_sarif(report: Report) -> dict[str, Any]:
    rules = [
        {
            "id": result.check_id,
            "name": result.title,
            "shortDescription": {"text": result.title},
            "fullDescription": {"text": result.summary},
            "properties": {"metrics": result.metrics},
        }
        for result in report.results
    ]

    uri = report.dataset_paths[0] if report.dataset_paths else "dataset"
    results: list[dict[str, Any]] = []
    for result in report.results:
        for finding in result.findings:
            line = (finding.row + 1) if finding.row is not None else 1
            results.append(
                {
                    "ruleId": result.check_id,
                    "level": LEVEL[result.severity.value],
                    "message": {"text": finding.message},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": uri},
                                "region": {"startLine": max(line, 1)},
                            }
                        }
                    ],
                    "properties": finding.detail,
                }
            )

    return {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "datasets-lint",
                        "informationUri": "https://github.com/horizonbymuneeb/datasets-lint",
                        "version": report.version,
                        "rules": rules,
                    }
                },
                "results": results,
                "properties": {
                    "verdict": report.worst.value,
                    "auditedRows": report.audited_rows,
                    "totalRows": report.total_rows,
                    "seed": report.seed,
                },
            }
        ],
    }


def write_sarif(report: Report, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(to_sarif(report), indent=2), encoding="utf-8")
    return out

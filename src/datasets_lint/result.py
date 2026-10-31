"""Result types shared by every check and report writer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    """Ordered severity: ok < warn < error."""

    OK = "ok"
    WARN = "warn"
    ERROR = "error"

    @property
    def rank(self) -> int:
        return {"ok": 0, "warn": 1, "error": 2}[self.value]

    def __ge__(self, other: object) -> bool:  # type: ignore[override]
        if isinstance(other, Severity):
            return self.rank >= other.rank
        return NotImplemented


@dataclass
class Finding:
    """A single problem located in the data.

    `message` is human readable and already redacted (never echo raw PII).
    `row` is the index inside the audited sample, or None for dataset-level findings.
    """

    message: str
    row: int | None = None
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class CheckResult:
    """Outcome of one check."""

    check_id: str
    title: str
    severity: Severity
    summary: str
    metrics: dict[str, Any] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    duration_s: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.check_id,
            "title": self.title,
            "severity": self.severity.value,
            "summary": self.summary,
            "metrics": self.metrics,
            "findings": [
                {"row": f.row, "message": f.message, "detail": f.detail} for f in self.findings
            ],
            "duration_s": round(self.duration_s, 3),
        }


@dataclass
class Report:
    """Everything we know after a run."""

    dataset_paths: list[str]
    total_rows: int
    audited_rows: int
    sample_size: int
    seed: int
    text_column: str | None
    label_column: str | None
    columns: list[str]
    results: list[CheckResult] = field(default_factory=list)
    version: str = "0.2.0"

    @property
    def worst(self) -> Severity:
        if not self.results:
            return Severity.OK
        return max((r.severity for r in self.results), key=lambda s: s.rank)

    def counts(self) -> dict[str, int]:
        out = {"ok": 0, "warn": 0, "error": 0}
        for r in self.results:
            out[r.severity.value] += 1
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": "datasets-lint",
            "version": self.version,
            "dataset": {
                "paths": self.dataset_paths,
                "total_rows": self.total_rows,
                "audited_rows": self.audited_rows,
                "sample_size": self.sample_size,
                "seed": self.seed,
                "columns": self.columns,
                "text_column": self.text_column,
                "label_column": self.label_column,
            },
            "verdict": self.worst.value,
            "counts": self.counts(),
            "checks": [r.to_dict() for r in self.results],
        }

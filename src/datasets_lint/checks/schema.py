"""Schema check: required columns, declared types and cardinality limits."""

from __future__ import annotations

from typing import Any

from datasets_lint.checks.base import Check, Context
from datasets_lint.dataset import Dataset
from datasets_lint.result import CheckResult, Finding, Severity

_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "float": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
}


class SchemaCheck(Check):
    id = "schema"
    title = "Schema"
    description = "Required columns, declared column types and cardinality limits."

    def run(self, ds: Dataset, ctx: Context) -> CheckResult:
        required = list(ctx.threshold(self.id, "required", []) or [])
        types = dict(ctx.threshold(self.id, "types", {}) or {})
        max_cardinality = dict(ctx.threshold(self.id, "max_cardinality", {}) or {})
        suppressed = ctx.suppressed_rows(self.id)

        findings: list[Finding] = []
        metrics: dict[str, Any] = {"columns": ds.columns, "required": required}

        missing = [col for col in required if col not in ds.columns]
        metrics["missing_columns"] = missing
        for col in missing:
            findings.append(Finding(message=f"required column missing: {col!r}"))

        kept = [r for i, r in enumerate(ds.rows) if i not in suppressed]
        type_errors: dict[str, int] = {}
        for col, expected in types.items():
            predicate = _TYPE_CHECKS.get(expected)
            if predicate is None:
                findings.append(Finding(message=f"unknown type {expected!r} declared for {col!r}"))
                continue
            if col not in ds.columns:
                continue
            bad = [
                i
                for i, row in enumerate(ds.rows)
                if i not in suppressed and row.get(col) is not None and not predicate(row.get(col))
            ]
            if bad:
                type_errors[col] = len(bad)
                findings.append(
                    Finding(
                        message=f"{len(bad):,} values in {col!r} are not {expected}",
                        row=bad[0],
                        detail={"column": col, "expected": expected, "sample_rows": bad[:5]},
                    )
                )
        metrics["type_errors"] = type_errors

        cardinality: dict[str, int] = {}
        violations: dict[str, int] = {}
        for col, limit in max_cardinality.items():
            if col not in ds.columns:
                continue
            values = {str(row.get(col)) for row in kept if row.get(col) is not None}
            cardinality[col] = len(values)
            if len(values) > int(limit):
                violations[col] = len(values)
                findings.append(
                    Finding(
                        message=f"{col!r} has {len(values):,} distinct values (limit {limit})",
                        detail={"column": col, "distinct": len(values), "limit": int(limit)},
                    )
                )
        metrics["cardinality"] = cardinality
        metrics["cardinality_violations"] = violations

        severity = Severity.OK
        if missing or type_errors:
            severity = Severity.ERROR
        elif violations:
            severity = Severity.WARN

        if missing:
            summary = f"missing required columns: {', '.join(missing)}"
        elif type_errors:
            summary = "type errors in " + ", ".join(type_errors)
        elif violations:
            summary = "cardinality exceeded in " + ", ".join(violations)
        else:
            summary = f"schema ok ({len(ds.columns)} columns)"

        return CheckResult(
            check_id=self.id,
            title=self.title,
            severity=severity,
            summary=summary,
            metrics=metrics,
            findings=findings,
        )

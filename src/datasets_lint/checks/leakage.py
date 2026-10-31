"""Label conflicts: the same text carrying different labels (label noise/leakage)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from datasets_lint.checks.base import Check, Context
from datasets_lint.dataset import Dataset, normalize
from datasets_lint.result import CheckResult, Finding, Severity


class LeakageCheck(Check):
    id = "leakage"
    title = "Label conflicts"
    description = "Identical texts annotated with different labels — label noise or leakage."

    def run(self, ds: Dataset, ctx: Context) -> CheckResult:
        if ds.label_column is None:
            return CheckResult(
                check_id=self.id,
                title=self.title,
                severity=Severity.OK,
                summary="no label column detected — skipped",
                metrics={"label_column": None},
            )

        suppressed = ctx.suppressed_rows(self.id)
        groups: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
        for i, text in ds.texts():
            if i in suppressed:
                continue
            norm = normalize(text)
            if not norm:
                continue
            label = ds.rows[i].get(ds.label_column)
            groups[norm][str(label)].append(i)

        conflicts = {text: labels for text, labels in groups.items() if len(labels) > 1}
        rows_in_conflict = sum(
            len(rows) for labels in conflicts.values() for rows in labels.values()
        )
        total = max(ds.audited_rows - len(suppressed), 1)
        pct = round(100.0 * rows_in_conflict / total, 3)

        max_pct = float(ctx.threshold(self.id, "max_conflict_pct", 1.0))
        metrics: dict[str, Any] = {
            "label_column": ds.label_column,
            "conflict_groups": len(conflicts),
            "rows_in_conflict": rows_in_conflict,
            "pct_in_conflict": pct,
        }

        findings: list[Finding] = []
        for text, labels in sorted(
            conflicts.items(), key=lambda kv: -sum(map(len, kv[1].values()))
        )[:25]:
            rows = sorted(row for group in labels.values() for row in group)
            pairs = ", ".join(f"{label}×{len(rs)}" for label, rs in labels.items())
            findings.append(
                Finding(
                    message=f'same text with {len(labels)} labels ({pairs}): "{text[:90]}…"',
                    row=rows[0],
                    detail={"rows": rows[:10], "labels": {k: len(v) for k, v in labels.items()}},
                )
            )

        severity = Severity.OK
        if pct > max_pct:
            severity = Severity.ERROR
        elif conflicts:
            severity = Severity.WARN

        summary = (
            f"{len(conflicts):,} texts with conflicting labels ({pct:.2f}% of rows)"
            if conflicts
            else "no label conflicts"
        )
        return CheckResult(
            check_id=self.id,
            title=self.title,
            severity=severity,
            summary=summary,
            metrics=metrics,
            findings=findings,
        )

"""Distribution sanity: empties, nulls, length outliers, label balance."""

from __future__ import annotations

from collections import Counter
from typing import Any

from datasets_lint.checks.base import Check, Context
from datasets_lint.dataset import Dataset, normalize
from datasets_lint.result import CheckResult, Finding, Severity


class StatsCheck(Check):
    id = "stats"
    title = "Distribution & shape"
    description = "Row counts, nulls, empty texts, length percentiles, label balance."

    def run(self, ds: Dataset, ctx: Context) -> CheckResult:
        suppressed = ctx.suppressed_rows(self.id)
        kept = [r for i, r in enumerate(ds.rows) if i not in suppressed]
        audited = max(len(kept), 1)
        findings: list[Finding] = []
        metrics: dict[str, Any] = {"rows": len(kept), "columns": len(ds.columns)}

        null_pct: dict[str, float] = {}
        for col in ds.columns:
            nulls = sum(1 for r in kept if r.get(col) is None)
            null_pct[col] = round(100.0 * nulls / audited, 3)
        metrics["null_pct"] = null_pct

        empty_rows = 0
        lengths: list[int] = []
        for i, text in ds.texts():
            if i in suppressed:
                continue
            norm = normalize(text)
            if not norm:
                empty_rows += 1
                findings.append(Finding(message="empty or whitespace-only text", row=i))
            lengths.append(len(norm))

        empty_pct = round(100.0 * empty_rows / audited, 3)
        metrics["empty_rows"] = empty_rows
        metrics["empty_pct"] = empty_pct
        metrics["text_column"] = ds.text_column

        if lengths:
            s = sorted(lengths)
            n = len(s)
            metrics["text_len"] = {
                "p50": s[n // 2],
                "p95": s[min(n - 1, int(n * 0.95))],
                "max": s[-1],
                "mean": round(sum(s) / n, 1),
            }
            metrics["n_unique_texts"] = len(
                {normalize(t) for i, t in ds.texts() if i not in suppressed}
            )

        if ds.label_column:
            counts = Counter(
                str(r.get(ds.label_column)) for r in kept if r.get(ds.label_column) is not None
            )
            total = sum(counts.values()) or 1
            balance = {k: round(100.0 * v / total, 2) for k, v in counts.most_common(20)}
            metrics["label_column"] = ds.label_column
            metrics["label_balance_pct"] = balance
            if len(balance) > 1:
                smallest = min(balance.values())
                if smallest < ctx.threshold(self.id, "min_label_pct", 1.0):
                    findings.append(
                        Finding(
                            message=f"rare label: {smallest:.2f}% of rows "
                            f"(threshold {ctx.threshold(self.id, 'min_label_pct', 1.0)}%)",
                            detail={"label_balance_pct": balance},
                        )
                    )

        max_empty = float(ctx.threshold(self.id, "max_empty_pct", 1.0))
        max_null = float(ctx.threshold(self.id, "max_null_pct", 50.0))

        severity = Severity.OK
        if empty_pct > max_empty:
            severity = Severity.ERROR
        elif any(v > max_null for v in null_pct.values()):
            severity = Severity.WARN

        worst_null = max(null_pct.values()) if null_pct else 0.0
        summary = (
            f"{len(kept):,} rows · {empty_pct:.2f}% empty · worst column {worst_null:.1f}% null"
        )
        if "text_len" in metrics:
            summary += f" · median {metrics['text_len']['p50']:,} chars"

        return CheckResult(
            check_id=self.id,
            title=self.title,
            severity=severity,
            summary=summary,
            metrics=metrics,
            findings=findings[:50],
        )

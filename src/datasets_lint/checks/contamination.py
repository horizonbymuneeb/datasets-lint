"""Eval-set contamination: does the dataset leak benchmark answers?

For every row we compute the share of its n-grams that already occur in an eval
set (containment). A row that reproduces a GSM8K question scores ~1.0; a row that
merely shares a common phrase scores near 0.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from datasets_lint.checks.base import Check, Context
from datasets_lint.dataset import Dataset, normalize
from datasets_lint.eval_sets import available, hash_ngram, load_eval_set, ngrams
from datasets_lint.result import CheckResult, Finding, Severity


@dataclass
class ContaminationAnalysis:
    per_set: dict[str, dict[str, Any]] = field(default_factory=dict)
    rows: dict[str, dict[int, float]] = field(default_factory=dict)
    """eval set name -> {row index: containment}"""
    total_rows: int = 0
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def contaminated_rows(self) -> list[int]:
        return sorted({row for hits in self.rows.values() for row in hits})


def _fingerprints(ctx: Context):
    names = list(ctx.threshold("contamination", "eval_sets", ["gsm8k", "humaneval", "mmlu"]))
    custom = dict(ctx.threshold("contamination", "custom_eval_sets", {}) or {})
    ngram = int(ctx.threshold("contamination", "ngram", 8))
    prints = [load_eval_set(name, ngram) for name in names]
    prints += [load_eval_set(name, ngram, custom_path=path) for name, path in custom.items()]
    return prints, ngram


def find_contaminated(ds: Dataset, ctx: Context) -> ContaminationAnalysis:
    """Score every row against every eval set. Shared by the check and the codemod."""
    fingerprints, ngram = _fingerprints(ctx)
    min_containment = float(ctx.threshold("contamination", "min_containment", 0.5))
    suppressed = ctx.suppressed_rows("contamination")
    total = max(ds.audited_rows - len(suppressed), 1)

    per_set: dict[str, dict[str, Any]] = {
        fp.name: {
            "eval_rows": fp.rows,
            "eval_ngrams": fp.size,
            "rows": 0,
            "max_containment": 0.0,
        }
        for fp in fingerprints
    }
    rows: dict[str, dict[int, float]] = {fp.name: {} for fp in fingerprints}

    for i, text in ds.texts():
        norm = normalize(text)
        if not norm or i in suppressed:
            continue
        row_grams = ngrams(norm, ngram)
        exact_hash = hash_ngram(norm)
        for fp in fingerprints:
            if exact_hash in fp.exact:
                containment = 1.0
            elif row_grams:
                containment = sum(1 for g in row_grams if g in fp.grams) / len(row_grams)
            else:
                continue
            if containment < min_containment:
                continue
            rows[fp.name][i] = round(containment, 4)
            stats = per_set[fp.name]
            stats["rows"] += 1
            stats["max_containment"] = max(stats["max_containment"], round(containment, 3))

    for stats in per_set.values():
        stats["pct"] = round(100.0 * stats["rows"] / total, 3)

    contaminated = {row for hits in rows.values() for row in hits}
    metrics: dict[str, Any] = {
        "ngram": ngram,
        "min_containment": min_containment,
        "rows_contaminated": len(contaminated),
        "pct_contaminated": round(100.0 * len(contaminated) / total, 3),
        "per_eval_set": per_set,
    }
    worst = max(per_set.values(), key=lambda s: s["pct"], default=None)
    if worst:
        metrics["worst_eval_set_pct"] = worst["pct"]

    return ContaminationAnalysis(per_set=per_set, rows=rows, total_rows=total, metrics=metrics)


class ContaminationCheck(Check):
    id = "contamination"
    title = "Eval-set contamination"
    description = "Rows that overlap public benchmarks (GSM8K, HumanEval) or your own eval sets."

    def run(self, ds: Dataset, ctx: Context) -> CheckResult:
        analysis = find_contaminated(ds, ctx)
        metrics = analysis.metrics
        max_pct = float(ctx.threshold(self.id, "max_contaminated_pct", 1.0))
        min_containment = metrics["min_containment"]

        findings: list[Finding] = []
        for set_name, hits in analysis.rows.items():
            for row, containment in sorted(hits.items(), key=lambda kv: -kv[1])[:25]:
                if len(findings) >= 50:
                    break
                text = normalize(ds.text(ds.rows[row]))[:110]
                findings.append(
                    Finding(
                        message=f'{containment:.0%} of this row appears in {set_name}: "{text}…"',
                        row=row,
                        detail={"eval_set": set_name, "containment": containment},
                    )
                )

        total_pct = metrics["pct_contaminated"]
        severity = Severity.OK
        if total_pct > max_pct:
            severity = Severity.ERROR
        elif metrics["rows_contaminated"] > 0:
            severity = Severity.WARN

        if metrics["rows_contaminated"]:
            parts = ", ".join(
                f"{name} {s['pct']:.2f}%" for name, s in analysis.per_set.items() if s["rows"]
            )
            summary = f"{total_pct:.2f}% of rows overlap an eval set ({parts})"
        else:
            summary = (
                f"no overlap with {', '.join(analysis.per_set)} "
                f"at {min_containment:.0%} containment"
            )

        return CheckResult(
            check_id=self.id,
            title=self.title,
            severity=severity,
            summary=summary,
            metrics=metrics,
            findings=findings,
        )


__all__ = ["ContaminationAnalysis", "ContaminationCheck", "available", "find_contaminated"]

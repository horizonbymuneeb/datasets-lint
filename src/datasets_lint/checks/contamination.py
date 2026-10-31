"""Eval-set contamination: does the dataset leak benchmark answers?

For every row we compute the share of its n-grams that already occur in an eval
set (containment). A row that reproduces a GSM8K question scores ~1.0; a row that
merely shares a common phrase scores near 0.
"""

from __future__ import annotations

from typing import Any

from datasets_lint.checks.base import Check, Context
from datasets_lint.dataset import Dataset, normalize
from datasets_lint.eval_sets import available, hash_ngram, load_eval_set, ngrams
from datasets_lint.result import CheckResult, Finding, Severity


class ContaminationCheck(Check):
    id = "contamination"
    title = "Eval-set contamination"
    description = "Rows that overlap public benchmarks (GSM8K, HumanEval) or your own eval sets."

    def run(self, ds: Dataset, ctx: Context) -> CheckResult:
        names = list(ctx.threshold(self.id, "eval_sets", ["gsm8k", "humaneval"]))
        custom = dict(ctx.threshold(self.id, "custom_eval_sets", {}) or {})
        ngram = int(ctx.threshold(self.id, "ngram", 8))
        min_containment = float(ctx.threshold(self.id, "min_containment", 0.5))
        max_pct = float(ctx.threshold(self.id, "max_contaminated_pct", 1.0))

        fingerprints = []
        for name in names:
            fingerprints.append(load_eval_set(name, ngram))
        for name, path in custom.items():
            fingerprints.append(load_eval_set(name, ngram, custom_path=path))

        total = max(ds.audited_rows, 1)
        per_set: dict[str, dict[str, Any]] = {
            fp.name: {
                "eval_rows": fp.rows,
                "eval_ngrams": fp.size,
                "rows": 0,
                "max_containment": 0.0,
            }
            for fp in fingerprints
        }
        contaminated_rows: set[int] = set()
        findings: list[Finding] = []

        for i, text in ds.texts():
            norm = normalize(text)
            if not norm:
                continue
            row_grams = ngrams(norm, ngram)
            exact_hash = hash_ngram(norm)

            for fp in fingerprints:
                if exact_hash in fp.exact:
                    containment = 1.0
                elif row_grams:
                    hits = sum(1 for g in row_grams if g in fp.grams)
                    containment = hits / len(row_grams)
                else:
                    continue
                if containment < min_containment:
                    continue

                contaminated_rows.add(i)
                stats = per_set[fp.name]
                stats["rows"] += 1
                stats["max_containment"] = max(stats["max_containment"], round(containment, 3))
                if len(findings) < 50:
                    findings.append(
                        Finding(
                            message=f"{containment:.0%} of this row appears in {fp.name}: "
                            f'"{norm[:110]}…"',
                            row=i,
                            detail={
                                "eval_set": fp.name,
                                "containment": round(containment, 3),
                            },
                        )
                    )

        for stats in per_set.values():
            stats["pct"] = round(100.0 * stats["rows"] / total, 3)

        total_contaminated = len(contaminated_rows)
        total_pct = round(100.0 * total_contaminated / total, 3)
        metrics: dict[str, Any] = {
            "ngram": ngram,
            "min_containment": min_containment,
            "rows_contaminated": total_contaminated,
            "pct_contaminated": total_pct,
            "per_eval_set": per_set,
        }
        worst_set = max(per_set.values(), key=lambda s: s["pct"], default=None)
        if worst_set:
            metrics["worst_eval_set_pct"] = worst_set["pct"]

        severity = Severity.OK
        if total_pct > max_pct:
            severity = Severity.ERROR
        elif total_contaminated > 0:
            severity = Severity.WARN

        if total_contaminated:
            parts = ", ".join(f"{name} {s['pct']:.2f}%" for name, s in per_set.items() if s["rows"])
            summary = f"{total_pct:.2f}% of rows overlap an eval set ({parts})"
        else:
            summary = (
                f"no overlap with {', '.join(fp.name for fp in fingerprints)} "
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


__all__ = ["ContaminationCheck", "available"]

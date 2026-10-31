"""Compare a run against a previous JSON report (`--baseline`)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from datasets_lint.result import Report, Severity

_RANK = {"ok": 0, "warn": 1, "error": 2}


def load_baseline(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if "checks" not in data:
        raise ValueError(f"{path} is not a datasets-lint JSON report")
    return data


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def diff_lines(report: Report, baseline: dict[str, Any]) -> list[str]:
    """Human-readable deltas: `dup.near_dup_pct 18.2 → 12.0 (-6.2) better`."""
    old = {c.get("id"): c for c in baseline.get("checks", [])}
    lines: list[str] = []

    old_rows = baseline.get("dataset", {}).get("audited_rows")
    if isinstance(old_rows, int) and old_rows != report.audited_rows:
        lines.append(f"audited rows: {old_rows:,} → {report.audited_rows:,}")

    for result in report.results:
        prev = old.get(result.check_id)
        if not prev:
            lines.append(f"{result.check_id}: new check (no baseline)")
            continue

        prev_sev = str(prev.get("severity", "ok"))
        now_sev = result.severity.value
        if _RANK[now_sev] != _RANK.get(prev_sev, 0):
            arrow = "better" if _RANK[now_sev] < _RANK.get(prev_sev, 0) else "WORSE"
            lines.append(f"{result.check_id}: severity {prev_sev} → {now_sev} ({arrow})")

        prev_metrics = prev.get("metrics", {})
        for key, value in result.metrics.items():
            before = _num(prev_metrics.get(key))
            after = _num(value)
            if before is None or after is None or before == after:
                continue
            delta = after - before
            lines.append(
                f"{result.check_id}.{key}: {before:,.3f} → {after:,.3f} "
                f"({delta:+,.3f}) {'better' if delta < 0 else 'worse'}"
            )

    if not lines:
        lines.append("no metric changes against baseline")
    return lines


def verdict_delta(report: Report, baseline: dict[str, Any]) -> Severity:
    """Return the baseline verdict if the run did not improve on it, else the new one."""
    try:
        prev = Severity(str(baseline.get("verdict", "ok")))
    except ValueError:
        return report.worst
    return prev if prev.rank > report.worst.rank else report.worst

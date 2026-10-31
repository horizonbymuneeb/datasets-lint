"""Codemods for datasets: deterministic, auditable repairs.

`--fix` never mutates the input. It plans every change first (so the report can
show what would happen), then writes a new file with the changes applied.

Fixers, in application order:

1. `dup`            drop every row but one per near-duplicate cluster
2. `stats`          drop empty / whitespace-only rows
3. `pii`            redact (default) or drop rows containing PII
4. `contamination`  drop rows that overlap an eval set (opt-in)
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import polars as pl

from datasets_lint.checks.base import Context
from datasets_lint.checks.contamination import find_contaminated
from datasets_lint.checks.dup import find_clusters
from datasets_lint.checks.pii import REDACTION, iter_matches
from datasets_lint.dataset import Dataset, normalize

ALL_FIXERS = ("dup", "stats", "pii", "contamination")


@dataclass
class FixPlan:
    drop: dict[str, list[int]] = field(default_factory=dict)
    redact: dict[int, list[tuple[int, int, str]]] = field(default_factory=dict)
    notes: dict[str, str] = field(default_factory=dict)

    @property
    def dropped_rows(self) -> set[int]:
        return {row for rows in self.drop.values() for row in rows}


@dataclass
class FixOutcome:
    rows: list[dict[str, Any]]
    stats: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return self.stats


def plan_fixes(
    ds: Dataset,
    ctx: Context,
    *,
    only: Iterable[str] | None = None,
    keep: str = "first",
    pii_action: str = "redact",
    drop_contaminated: bool = False,
) -> FixPlan:
    """Compute every change without touching the data."""
    selected = [f for f in ALL_FIXERS if only is None or f in set(only)]
    unknown = set(only or ()) - set(ALL_FIXERS)
    if unknown:
        raise ValueError(f"unknown fixer(s): {', '.join(sorted(unknown))}")

    plan = FixPlan()

    if "dup" in selected:
        dup_analysis = find_clusters(ds, ctx)
        dropped: list[int] = []
        for members in dup_analysis.clusters:
            ordered = sorted(members, reverse=(keep == "last"))
            dropped.extend(ordered[1:])
        plan.drop["dup"] = sorted(dropped)
        plan.notes["dup"] = f"{len(dup_analysis.clusters)} clusters, keeping the {keep} row"

    if "stats" in selected:
        empty = [i for i, text in ds.texts() if not normalize(text)]
        plan.drop["stats"] = empty
        plan.notes["stats"] = "dropped empty or whitespace-only rows"

    if "pii" in selected:
        hits: dict[int, list[tuple[int, int, str]]] = {}
        for i, text in ds.texts():
            for match in iter_matches(text):
                hits.setdefault(i, []).append(
                    (match.start, match.end, REDACTION.get(match.kind, "[REDACTED]"))
                )
        if pii_action == "drop":
            plan.drop["pii"] = sorted(hits)
            plan.notes["pii"] = "dropped rows containing PII"
        else:
            plan.redact = hits
            plan.notes["pii"] = "redacted PII in place"

    if "contamination" in selected and drop_contaminated:
        contam = find_contaminated(ds, ctx)
        plan.drop["contamination"] = contam.contaminated_rows
        plan.notes["contamination"] = "dropped rows overlapping an eval set"

    return plan


def _redact_row(
    row: dict[str, Any], column: str, edits: list[tuple[int, int, str]]
) -> dict[str, Any]:
    text = row.get(column)
    if text is None:
        return row
    value = str(text)
    for start, end, replacement in sorted(edits, key=lambda e: e[0], reverse=True):
        value = value[:start] + replacement + value[end:]
    return {**row, column: value}


def apply_fixes(ds: Dataset, plan: FixPlan) -> FixOutcome:
    """Return the cleaned rows plus an audit trail."""
    dropped = plan.dropped_rows
    out: list[dict[str, Any]] = []
    redactions: dict[str, int] = {}

    for i, row in enumerate(ds.rows):
        if i in dropped:
            continue
        edits = plan.redact.get(i)
        if edits and ds.text_column:
            for _, _, replacement in edits:
                kind = replacement.strip("[]").removeprefix("REDACTED_").lower()
                redactions[kind] = redactions.get(kind, 0) + 1
            row = _redact_row(row, ds.text_column, edits)
        out.append(row)

    stats: dict[str, Any] = {
        "input_rows": ds.audited_rows,
        "output_rows": len(out),
        "dropped_rows": len(dropped),
        "dropped_by_fixer": {name: len(rows) for name, rows in plan.drop.items() if rows},
        "redactions": redactions,
        "notes": plan.notes,
    }
    return FixOutcome(rows=out, stats=stats)


def write_dataset(rows: list[dict[str, Any]], path: str | Path, columns: list[str]) -> Path:
    """Write rows in the format implied by the extension (default: JSONL)."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    suffix = out.suffix.lower()
    frame = pl.DataFrame(rows, infer_schema_length=None) if rows else pl.DataFrame()
    if rows and columns:
        keep = [c for c in columns if c in frame.columns]
        if keep:
            frame = frame.select(keep)

    if suffix in (".jsonl", ".ndjson", ""):
        with out.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    elif suffix == ".json":
        out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    elif suffix == ".csv":
        frame.write_csv(out)
    elif suffix in (".parquet", ".pq"):
        frame.write_parquet(out)
    else:
        raise ValueError(
            f"cannot infer output format from {out.suffix!r}; use .jsonl, .json, .csv or .parquet"
        )
    return out

"""Dataset loading, sampling and text/label column inference."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import polars as pl

TEXT_HINTS = (
    "text",
    "content",
    "document",
    "passage",
    "article",
    "body",
    "prompt",
    "instruction",
    "question",
    "input",
    "output",
    "completion",
    "answer",
    "response",
    "code",
    "sentence",
    "translation",
    "summary",
)

LABEL_HINTS = (
    "label",
    "labels",
    "target",
    "targets",
    "class",
    "category",
    "intent",
    "topic",
    "sentiment",
)

SUPPORTED = {
    ".jsonl": "ndjson",
    ".ndjson": "ndjson",
    ".json": "json",
    ".csv": "csv",
    ".parquet": "parquet",
    ".pq": "parquet",
}


class DatasetError(ValueError):
    """Raised for unreadable or unsupported datasets."""


@dataclass
class Dataset:
    """A sampled view of one or more dataset files.

    Rows are plain dicts. When several files are given, every row gets a
    ``__source`` key so checks can report cross-split duplicates.
    """

    paths: list[Path]
    columns: list[str]
    rows: list[dict[str, Any]]
    total_rows: int
    text_column: str | None = None
    label_column: str | None = None
    sources: list[str] = field(default_factory=list)

    @property
    def audited_rows(self) -> int:
        return len(self.rows)

    def text(self, row: dict[str, Any]) -> str:
        if self.text_column is None:
            return ""
        value = row.get(self.text_column)
        if value is None:
            return ""
        return str(value)

    def texts(self) -> Iterator[tuple[int, str]]:
        for i, row in enumerate(self.rows):
            yield i, self.text(row)

    def source_of(self, row: dict[str, Any]) -> str:
        return str(row.get("__source", self.paths[0].name))


def _read(path: Path) -> pl.DataFrame:
    kind = SUPPORTED.get(path.suffix.lower())
    if kind is None:
        raise DatasetError(
            f"unsupported file type {path.suffix!r} for {path}; "
            f"supported: {', '.join(sorted(SUPPORTED))}"
        )
    if not path.exists():
        raise DatasetError(f"no such file: {path}")
    try:
        if kind == "ndjson":
            return pl.read_ndjson(path)
        if kind == "json":
            return pl.read_json(path)
        if kind == "csv":
            return pl.read_csv(path, infer_schema_length=10_000)
        return pl.read_parquet(path)
    except Exception as exc:  # pragma: no cover - depends on file content
        raise DatasetError(f"could not read {path}: {exc}") from exc


def _guess_text_column(df: pl.DataFrame) -> str | None:
    best: tuple[float, str] | None = None
    for name in df.columns:
        if name == "__source":
            continue
        col = df[name]
        if col.dtype != pl.String and col.dtype != pl.Categorical:
            continue
        hint = 1.0 if any(h in name.lower() for h in TEXT_HINTS) else 0.0
        try:
            sample = col.drop_nulls().head(200).cast(pl.String)
            avg_len = (sample.str.len_chars().mean() or 0.0) if sample.len() else 0.0
        except Exception:
            avg_len = 0.0
        score = hint * 10_000 + float(avg_len)
        if best is None or score > best[0]:
            best = (score, name)
    return best[1] if best else None


def _guess_label_column(df: pl.DataFrame, text_column: str | None) -> str | None:
    for name in df.columns:
        if name in ("__source", text_column):
            continue
        if any(h == name.lower() or name.lower().endswith(h) for h in LABEL_HINTS):
            return name
    # Fall back to the first low-cardinality non-text column.
    for name in df.columns:
        if name in ("__source", text_column):
            continue
        try:
            n_unique = df[name].n_unique()
        except Exception:
            continue
        if 1 < n_unique <= 64:
            return name
    return None


def load_dataset(
    paths: list[str | Path],
    *,
    sample: int = 100_000,
    seed: int = 0,
    text_column: str | None = None,
    label_column: str | None = None,
) -> Dataset:
    """Load and sample one or more dataset files."""
    resolved = [Path(p).expanduser() for p in paths]
    if not resolved:
        raise DatasetError("no input files given")

    frames: list[pl.DataFrame] = []
    total = 0
    for path in resolved:
        df = _read(path)
        total += df.height
        if len(resolved) > 1:
            df = df.with_columns(pl.lit(path.name).alias("__source"))
        frames.append(df)

    df = pl.concat(frames, how="diagonal_relaxed") if len(frames) > 1 else frames[0]

    if df.height > sample:
        df = df.sample(n=sample, seed=seed, shuffle=True)

    columns = [c for c in df.columns if c != "__source"]
    text_col = text_column or _guess_text_column(df)
    if text_column and text_column not in df.columns:
        raise DatasetError(
            f"text column {text_column!r} not found; available: {', '.join(columns)}"
        )
    label_col = label_column or _guess_label_column(df, text_col)

    return Dataset(
        paths=resolved,
        columns=columns,
        rows=df.to_dicts(),
        total_rows=total,
        text_column=text_col,
        label_column=label_col,
        sources=[p.name for p in resolved],
    )


_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Lowercase and collapse whitespace — the canonical form used by `dup`."""
    return _WS.sub(" ", text.lower()).strip()

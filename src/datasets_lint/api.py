"""Public programmatic API. Stable from v1.0."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from datasets_lint.checks.base import Context
from datasets_lint.config import Config, load_config
from datasets_lint.dataset import Dataset, load_dataset
from datasets_lint.engine import build_report, resolve_checks, run_checks
from datasets_lint.fixers import apply_fixes, plan_fixes, write_dataset
from datasets_lint.result import Report


def _load(
    paths: str | Path | Iterable[str | Path],
    config: Config | None = None,
    config_path: str | Path | None = None,
    profile: str | None = None,
) -> tuple[Dataset, Config]:
    cfg = config or load_config(config_path, profile=profile)
    items = [paths] if isinstance(paths, (str, Path)) else list(paths)
    ds = load_dataset(
        items,
        sample=cfg.sample,
        seed=cfg.seed,
        text_column=cfg.text_column,
        label_column=cfg.label_column,
    )
    return ds, cfg


def audit(
    paths: str | Path | Iterable[str | Path],
    *,
    config: Config | None = None,
    config_path: str | Path | None = None,
    profile: str | None = None,
    checks: list[str] | None = None,
    exclude: list[str] | None = None,
) -> Report:
    """Audit one or more dataset files and return a `Report`.

    >>> report = audit("train.jsonl", profile="strict")
    >>> report.worst.value
    'error'
    """
    ds, cfg = _load(paths, config, config_path, profile)
    selected = resolve_checks(checks, exclude, include_plugins=cfg.plugins)
    results = run_checks(ds, cfg, selected)
    return build_report(ds, cfg, results)


def fix(
    paths: str | Path | Iterable[str | Path],
    out: str | Path,
    *,
    config: Config | None = None,
    config_path: str | Path | None = None,
    profile: str | None = None,
    only: list[str] | None = None,
    keep: str = "first",
    pii_action: str = "redact",
    drop_contaminated: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Write a repaired copy of the dataset and return the audit trail."""
    ds, cfg = _load(paths, config, config_path, profile)
    plan = plan_fixes(
        ds,
        Context(config=cfg, seed=cfg.seed),
        only=only,
        keep=keep,
        pii_action=pii_action,
        drop_contaminated=drop_contaminated,
    )
    outcome = apply_fixes(ds, plan)
    stats: dict[str, Any] = dict(outcome.stats)
    if dry_run:
        stats["dry_run"] = True
    else:
        stats["output"] = str(write_dataset(outcome.rows, out, ds.columns))
    return stats

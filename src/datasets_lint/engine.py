"""Runs the selected checks and assembles a Report."""

from __future__ import annotations

import time

from datasets_lint import __version__
from datasets_lint.checks import ALL_CHECKS, CHECKS_BY_ID, Context
from datasets_lint.config import Config
from datasets_lint.dataset import Dataset
from datasets_lint.result import CheckResult, Report


class UnknownCheck(ValueError):
    pass


def resolve_checks(only: list[str] | None, exclude: list[str] | None) -> list:
    selected = list(ALL_CHECKS)
    if only:
        missing = [c for c in only if c not in CHECKS_BY_ID]
        if missing:
            raise UnknownCheck(
                f"unknown check(s): {', '.join(missing)}; available: {', '.join(CHECKS_BY_ID)}"
            )
        selected = [CHECKS_BY_ID[c] for c in only]
    if exclude:
        selected = [c for c in selected if c.id not in exclude]
    return selected


def run_checks(ds: Dataset, cfg: Config, checks: list) -> list[CheckResult]:
    ctx = Context(config=cfg, seed=cfg.seed)
    results: list[CheckResult] = []
    for check in checks:
        started = time.perf_counter()
        result = check.run(ds, ctx)
        result.duration_s = time.perf_counter() - started
        results.append(result)
    return results


def build_report(ds: Dataset, cfg: Config, results: list[CheckResult]) -> Report:
    return Report(
        dataset_paths=[str(p) for p in ds.paths],
        total_rows=ds.total_rows,
        audited_rows=ds.audited_rows,
        sample_size=cfg.sample,
        seed=cfg.seed,
        text_column=ds.text_column,
        label_column=ds.label_column,
        columns=ds.columns,
        results=results,
        version=__version__,
    )

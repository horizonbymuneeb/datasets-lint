"""Check registry: built-in checks plus third-party plugins via entry points."""

from __future__ import annotations

from functools import lru_cache
from importlib.metadata import entry_points

from datasets_lint.checks.base import Check, Context
from datasets_lint.checks.contamination import ContaminationCheck
from datasets_lint.checks.dup import DupCheck
from datasets_lint.checks.leakage import LeakageCheck
from datasets_lint.checks.pii import PiiCheck
from datasets_lint.checks.schema import SchemaCheck
from datasets_lint.checks.stats import StatsCheck

ALL_CHECKS: list[Check] = [
    StatsCheck(),
    DupCheck(),
    PiiCheck(),
    ContaminationCheck(),
    SchemaCheck(),
    LeakageCheck(),
]

ENTRY_POINT_GROUP = "datasets_lint.checks"


@lru_cache(maxsize=1)
def discover_plugins() -> tuple[Check, ...]:
    """Load third-party checks: `[project.entry-points."datasets_lint.checks"]`."""
    found: list[Check] = []
    for entry in entry_points(group=ENTRY_POINT_GROUP):
        try:
            loaded = entry.load()
            check = loaded() if isinstance(loaded, type) else loaded
        except Exception:  # pragma: no cover - broken plugin must not kill the run
            continue
        if isinstance(check, Check) and check.id:
            found.append(check)
    return tuple(found)


def all_checks(include_plugins: bool = True) -> list[Check]:
    checks = list(ALL_CHECKS)
    if include_plugins:
        known = {c.id for c in checks}
        checks.extend(c for c in discover_plugins() if c.id not in known)
    return checks


def checks_by_id(include_plugins: bool = True) -> dict[str, Check]:
    return {check.id: check for check in all_checks(include_plugins)}


CHECKS_BY_ID: dict[str, Check] = {c.id: c for c in ALL_CHECKS}

__all__ = [
    "ALL_CHECKS",
    "CHECKS_BY_ID",
    "Check",
    "Context",
    "all_checks",
    "checks_by_id",
    "discover_plugins",
]

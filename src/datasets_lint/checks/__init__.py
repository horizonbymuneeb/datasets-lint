"""Check registry. Add a new check by importing it and appending an instance."""

from __future__ import annotations

from datasets_lint.checks.base import Check, Context
from datasets_lint.checks.dup import DupCheck
from datasets_lint.checks.pii import PiiCheck
from datasets_lint.checks.stats import StatsCheck

ALL_CHECKS: list[Check] = [
    StatsCheck(),
    DupCheck(),
    PiiCheck(),
]

CHECKS_BY_ID: dict[str, Check] = {c.id: c for c in ALL_CHECKS}

__all__ = ["ALL_CHECKS", "CHECKS_BY_ID", "Check", "Context"]

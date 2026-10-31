"""Check protocol and the context every check receives."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from datasets_lint.config import Config
from datasets_lint.dataset import Dataset
from datasets_lint.result import CheckResult


@dataclass
class Context:
    config: Config
    seed: int = 0

    def threshold(self, check_id: str, key: str, default: Any) -> Any:
        return self.config.threshold(check_id, key, default)


class Check(ABC):
    """A single data-quality check.

    Subclass, set ``id``/``title``/``description``, implement ``run`` and add an
    instance to ``datasets_lint.checks.ALL_CHECKS``. That is the whole plugin API.
    """

    id: str = ""
    title: str = ""
    description: str = ""

    @abstractmethod
    def run(self, ds: Dataset, ctx: Context) -> CheckResult: ...

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Check {self.id}>"

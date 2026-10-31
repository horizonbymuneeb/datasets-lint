"""Configuration loading (`datasets-lint.toml`) and defaults."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):  # pragma: no cover - version dependent
    import tomllib
else:  # pragma: no cover - version dependent
    import tomli as tomllib

CONFIG_FILENAME = "datasets-lint.toml"


@dataclass
class Config:
    sample: int = 100_000
    seed: int = 0
    fail_on: str = "error"  # "none" | "warn" | "error"
    text_column: str | None = None
    label_column: str | None = None
    checks: dict[str, dict[str, Any]] = field(default_factory=dict)

    def for_check(self, check_id: str) -> dict[str, Any]:
        return self.checks.get(check_id, {})

    def threshold(self, check_id: str, key: str, default: Any) -> Any:
        return self.for_check(check_id).get(key, default)


def find_config(explicit: str | Path | None) -> Path | None:
    if explicit:
        path = Path(explicit).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"config file not found: {path}")
        return path
    for candidate in (Path.cwd() / CONFIG_FILENAME, Path.cwd() / ".datasets-lint.toml"):
        if candidate.exists():
            return candidate
    return None


def load_config(explicit: str | Path | None = None) -> Config:
    path = find_config(explicit)
    if path is None:
        return Config()
    with path.open("rb") as fh:
        data = tomllib.load(fh)

    defaults = data.get("defaults", {})
    cfg = Config(
        sample=int(defaults.get("sample", 100_000)),
        seed=int(defaults.get("seed", 0)),
        fail_on=str(defaults.get("fail_on", "error")),
        text_column=defaults.get("text_column"),
        label_column=defaults.get("label_column"),
        checks={k: dict(v) for k, v in data.get("checks", {}).items()},
    )
    if cfg.fail_on not in ("none", "warn", "error"):
        raise ValueError(f"invalid fail_on {cfg.fail_on!r}; expected none|warn|error")
    return cfg

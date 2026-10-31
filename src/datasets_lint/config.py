"""Configuration loading (`datasets-lint.toml`), profiles and suppressions."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):  # pragma: no cover - version dependent
    import tomllib
else:  # pragma: no cover - version dependent
    import tomli as tomllib

CONFIG_FILENAME = "datasets-lint.toml"
PROFILES = ("default", "strict", "ci", "dev")

# Profiles are applied first, user config on top, CLI flags on top of that.
PROFILE_PRESETS: dict[str, dict[str, Any]] = {
    "default": {},
    "strict": {
        "fail_on": "warn",
        "checks": {
            "dup": {"max_near_dup_pct": 0.5},
            "pii": {"max_warn_findings_pct": 0.5},
            "contamination": {"max_contaminated_pct": 0.1},
            "stats": {"max_empty_pct": 0.1},
        },
    },
    "ci": {"fail_on": "error"},
    "dev": {"fail_on": "none"},
}


@dataclass
class Suppression:
    """An auditable, expiring exception for specific rows of one check."""

    check: str
    rows: list[int]
    reason: str = ""
    expires: date | None = None

    def is_expired(self, today: date | None = None) -> bool:
        if self.expires is None:
            return False
        return (today or date.today()) > self.expires

    def to_dict(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "rows": self.rows,
            "reason": self.reason,
            "expires": self.expires.isoformat() if self.expires else None,
        }


@dataclass
class Config:
    sample: int = 100_000
    seed: int = 0
    fail_on: str = "error"  # "none" | "warn" | "error"
    profile: str = "default"
    text_column: str | None = None
    label_column: str | None = None
    checks: dict[str, dict[str, Any]] = field(default_factory=dict)
    suppressions: list[Suppression] = field(default_factory=list)
    plugins: bool = True

    def for_check(self, check_id: str) -> dict[str, Any]:
        return self.checks.get(check_id, {})

    def threshold(self, check_id: str, key: str, default: Any) -> Any:
        return self.for_check(check_id).get(key, default)

    def suppressed_rows(self, check_id: str) -> dict[int, Suppression]:
        out: dict[int, Suppression] = {}
        for suppression in self.suppressions:
            if suppression.check in (check_id, "*") and not suppression.is_expired():
                for row in suppression.rows:
                    out[row] = suppression
        return out


def _merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


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


def _parse_suppressions(raw: list[dict[str, Any]]) -> list[Suppression]:
    out: list[Suppression] = []
    for item in raw:
        if "check" not in item or "rows" not in item:
            raise ValueError("each [[suppress]] entry needs `check` and `rows`")
        rows = item["rows"]
        if not isinstance(rows, list) or not all(isinstance(r, int) for r in rows):
            raise ValueError("`rows` in [[suppress]] must be a list of integers")
        expires = item.get("expires")
        out.append(
            Suppression(
                check=str(item["check"]),
                rows=list(rows),
                reason=str(item.get("reason", "")),
                expires=date.fromisoformat(str(expires)) if expires else None,
            )
        )
    return out


def load_config(explicit: str | Path | None = None, profile: str | None = None) -> Config:
    path = find_config(explicit)
    data: dict[str, Any] = {}
    if path is not None:
        with path.open("rb") as fh:
            data = tomllib.load(fh)

    defaults = data.get("defaults", {})
    chosen = profile or defaults.get("profile", "default")
    if chosen not in PROFILES:
        raise ValueError(f"unknown profile {chosen!r}; expected one of {', '.join(PROFILES)}")

    preset = PROFILE_PRESETS[chosen]
    merged = _merge(preset, defaults)

    cfg = Config(
        sample=int(merged.get("sample", 100_000)),
        seed=int(merged.get("seed", 0)),
        fail_on=str(merged.get("fail_on", "error")),
        profile=chosen,
        text_column=merged.get("text_column"),
        label_column=merged.get("label_column"),
        checks=_merge(preset.get("checks", {}), data.get("checks", {})),
        suppressions=_parse_suppressions(data.get("suppress", [])),
        plugins=bool(merged.get("plugins", True)),
    )
    if cfg.fail_on not in ("none", "warn", "error"):
        raise ValueError(f"invalid fail_on {cfg.fail_on!r}; expected none|warn|error")
    return cfg

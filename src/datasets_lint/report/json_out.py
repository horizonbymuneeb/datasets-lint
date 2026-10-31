"""Machine-readable JSON output (stable schema, versioned by tool version)."""

from __future__ import annotations

import json
from pathlib import Path

from datasets_lint.result import Report


def write_json(report: Report, path: str | Path | None = None) -> str:
    payload = json.dumps(report.to_dict(), indent=2, ensure_ascii=False, default=str)
    if path is not None:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload, encoding="utf-8")
    return payload

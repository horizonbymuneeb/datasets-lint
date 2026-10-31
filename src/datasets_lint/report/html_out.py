"""Single-file HTML report — no CDN, no JavaScript, opens offline."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Any

from jinja2 import Environment

from datasets_lint.result import Report

_TEMPLATE = "templates/report.html.j2"


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:,.3f}".rstrip("0").rstrip(".")
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, dict):
        return " · ".join(f"{k}: {_fmt(v)}" for k, v in list(value.items())[:8])
    if isinstance(value, list):
        head = ", ".join(_fmt(v) for v in value[:6])
        return head + (f", … +{len(value) - 6}" if len(value) > 6 else "")
    return str(value)


def _bars(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    """Turn a `*_pct` dict metric into horizontal bars for the template."""
    out: list[dict[str, Any]] = []
    for key, value in metrics.items():
        if (
            isinstance(value, dict)
            and value
            and all(isinstance(v, (int, float)) for v in value.values())
        ):
            top = sorted(value.items(), key=lambda kv: -float(kv[1]))[:12]
            peak = max(float(v) for _, v in top) or 1.0
            out.append(
                {
                    "title": key.replace("_", " "),
                    "rows": [
                        {
                            "label": str(k),
                            "value": _fmt(v),
                            "width": round(100 * float(v) / peak, 1),
                        }
                        for k, v in top
                    ],
                }
            )
    return out


def _view(report: Report) -> dict[str, Any]:
    env = Environment(autoescape=True)
    template = env.from_string(
        files("datasets_lint.report").joinpath(_TEMPLATE).read_text(encoding="utf-8")
    )
    counts = report.counts()
    checks = []
    shown = 12
    for r in report.results:
        metrics = {k: _fmt(v) for k, v in r.metrics.items()}
        checks.append(
            {
                "id": r.check_id,
                "title": r.title,
                "severity": r.severity.value,
                "summary": r.summary,
                "duration": f"{r.duration_s:.2f}s",
                "metrics": metrics,
                "bars": _bars(r.metrics),
                "findings": [
                    {"row": f.row, "message": f.message, "detail": _fmt(f.detail)}
                    for f in r.findings[:shown]
                ],
                "findings_total": len(r.findings),
                "shown": min(shown, len(r.findings)),
            }
        )
    return template.render(
        version=report.version,
        paths=", ".join(report.dataset_paths),
        total_rows=f"{report.total_rows:,}",
        audited_rows=f"{report.audited_rows:,}",
        seed=report.seed,
        text_column=report.text_column or "—",
        label_column=report.label_column or "—",
        verdict=report.worst.value,
        counts=counts,
        checks=checks,
        total_time=f"{sum(r.duration_s for r in report.results):.2f}s",
    )


def render_html(report: Report) -> str:
    return _view(report)


def write_html(report: Report, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(report), encoding="utf-8")
    return out

"""Report writers."""

from __future__ import annotations

from datasets_lint.report.html_out import write_html
from datasets_lint.report.json_out import write_json

__all__ = ["write_html", "write_json"]

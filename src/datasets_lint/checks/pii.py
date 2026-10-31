"""PII detection: high-confidence secrets and warn-level contact data."""

from __future__ import annotations

import re
from typing import Any

from datasets_lint.checks.base import Check, Context
from datasets_lint.dataset import Dataset
from datasets_lint.result import CheckResult, Finding, Severity

# (kind, severity, pattern). Patterns are intentionally conservative: a false
# positive on a phone number is annoying, a false negative on an API key is an
# incident. High-confidence secrets default to `error`.
PATTERNS: list[tuple[str, Severity, re.Pattern[str]]] = [
    (
        "api_key",
        Severity.ERROR,
        re.compile(
            r"\b(?:sk-[A-Za-z0-9]{16,}|sk-ant-[A-Za-z0-9_\-]{16,}|"
            r"AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|gho_[A-Za-z0-9]{36}|"
            r"xox[baprs]-[A-Za-z0-9\-]{10,}|AIza[0-9A-Za-z_\-]{35})\b"
        ),
    ),
    (
        "private_key",
        Severity.ERROR,
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
    ("iban", Severity.ERROR, re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")),
    ("ssn", Severity.ERROR, re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")),
    (
        "email",
        Severity.WARN,
        re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
    ),
    (
        "phone",
        Severity.WARN,
        re.compile(
            r"(?<![\d.])(?:\+\d{1,3}[\s.\-]?)?(?:\(\d{2,4}\)[\s.\-]?)?\d{3,4}[\s.\-]\d{3,4}(?![\d.])"
        ),
    ),
    (
        "ipv4",
        Severity.WARN,
        re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"),
    ),
]

# Common false positives for the phone pattern (dates, versions, ranges).
_PHONE_FALSE_POSITIVES = re.compile(r"^(?:19|20)\d{2}[\s.\-]\d{1,2}[\s.\-]\d{1,2}$|^\d+\.\d+\.\d+$")


def redact(value: str) -> str:
    """Keep the shape, hide the payload: `a***@example.com`, `sk-***`, ..."""
    if len(value) <= 4:
        return "*" * len(value)
    if "@" in value:
        local, _, domain = value.partition("@")
        return f"{local[:1]}***@{domain}"
    if re.fullmatch(r"[A-Za-z0-9_\-]+", value) and len(value) > 12:
        return f"{value[:4]}***"
    return f"{value[:2]}***{value[-2:]}"


class PiiCheck(Check):
    id = "pii"
    title = "PII & secrets"
    description = "Emails, phones, IPs, IBANs, SSNs and API keys. Findings are redacted."

    def run(self, ds: Dataset, ctx: Context) -> CheckResult:
        max_error_pct = float(ctx.threshold(self.id, "max_error_findings_pct", 0.1))
        max_warn_pct = float(ctx.threshold(self.id, "max_warn_findings_pct", 5.0))

        counts: dict[str, int] = {}
        by_severity: dict[str, int] = {"warn": 0, "error": 0}
        findings: list[Finding] = []
        affected_rows = 0

        for i, text in ds.texts():
            if not text:
                continue
            row_hit = False
            for kind, severity, pattern in PATTERNS:
                for match in pattern.finditer(text):
                    value = match.group(0)
                    if kind == "phone" and _PHONE_FALSE_POSITIVES.match(value.strip()):
                        continue
                    if kind == "iban" and not re.search(r"\d", value):
                        continue
                    row_hit = True
                    counts[kind] = counts.get(kind, 0) + 1
                    by_severity[severity.value] += 1
                    if len(findings) < 50:
                        findings.append(
                            Finding(
                                message=f"{kind}: {redact(value)}",
                                row=i,
                                detail={"kind": kind, "severity": severity.value},
                            )
                        )
            if row_hit:
                affected_rows += 1

        total = max(ds.audited_rows, 1)
        affected_pct = round(100.0 * affected_rows / total, 3)
        metrics: dict[str, Any] = {
            "rows_with_pii": affected_rows,
            "rows_with_pii_pct": affected_pct,
            "findings_by_kind": counts,
            "findings_by_severity": by_severity,
        }

        severity = Severity.OK
        if by_severity["error"] > 0 and affected_pct > max_error_pct:
            severity = Severity.ERROR
        elif affected_pct > max_warn_pct or by_severity["error"] > 0:
            severity = Severity.WARN

        if counts:
            parts = ", ".join(f"{k} {v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))
            summary = f"{affected_pct:.2f}% of rows contain PII ({parts})"
        else:
            summary = "no PII patterns found"

        return CheckResult(
            check_id=self.id,
            title=self.title,
            severity=severity,
            summary=summary,
            metrics=metrics,
            findings=findings,
        )

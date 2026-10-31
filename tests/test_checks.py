from pathlib import Path

import pytest

from datasets_lint.checks import CHECKS_BY_ID, Context
from datasets_lint.checks.pii import redact
from datasets_lint.config import Config
from datasets_lint.dataset import load_dataset
from datasets_lint.result import Severity

FIXTURES = Path(__file__).parent / "fixtures"


def ctx(**thresholds) -> Context:
    cfg = Config(checks={k.split("__")[0]: {k.split("__")[1]: v} for k, v in thresholds.items()})
    return Context(config=cfg)


def test_stats_flags_empty_rows():
    ds = load_dataset([FIXTURES / "dirty.jsonl"])
    result = CHECKS_BY_ID["stats"].run(ds, ctx())
    assert result.metrics["empty_rows"] == 2
    assert result.severity is Severity.ERROR
    assert any("empty" in f.message for f in result.findings)


def test_stats_clean_dataset_is_ok():
    ds = load_dataset([FIXTURES / "clean.jsonl"])
    result = CHECKS_BY_ID["stats"].run(ds, ctx())
    assert result.metrics["empty_rows"] == 0
    assert result.metrics["text_len"]["p50"] > 0


def test_dup_finds_exact_and_near_duplicates():
    ds = load_dataset([FIXTURES / "dirty.jsonl"])
    result = CHECKS_BY_ID["dup"].run(ds, ctx())
    assert result.metrics["exact_dup_rows"] >= 2
    assert result.metrics["near_dup_rows"] >= 3
    assert result.severity is Severity.ERROR
    assert result.findings


def test_dup_clean_dataset_has_no_clusters():
    ds = load_dataset([FIXTURES / "clean.jsonl"])
    result = CHECKS_BY_ID["dup"].run(ds, ctx())
    assert result.metrics["near_dup_rows"] == 0
    assert result.severity is Severity.OK


def test_dup_reports_cross_file_overlap():
    ds = load_dataset([FIXTURES / "clean.jsonl", FIXTURES / "dirty.jsonl"])
    result = CHECKS_BY_ID["dup"].run(ds, ctx())
    assert result.metrics["cross_source_dup_rows"] > 0


def test_pii_detects_and_redacts():
    ds = load_dataset([FIXTURES / "dirty.jsonl"])
    result = CHECKS_BY_ID["pii"].run(ds, ctx())
    kinds = result.metrics["findings_by_kind"]
    assert kinds.get("email") == 1
    assert kinds.get("phone") == 1
    assert kinds.get("api_key") == 1
    assert result.severity is Severity.ERROR
    joined = " ".join(f.message for f in result.findings)
    assert "jane.doe@example.com" not in joined
    assert "j***@example.com" in joined
    assert "555-867-5309" not in joined


def test_pii_clean_dataset_is_ok():
    ds = load_dataset([FIXTURES / "clean.jsonl"])
    result = CHECKS_BY_ID["pii"].run(ds, ctx())
    assert result.severity is Severity.OK
    assert result.findings == []


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("jane.doe@example.com", "j***@example.com"),
        ("sk-abcdefghijklmnopqrstuvwxyz", "sk-a***"),
        ("abc", "***"),
    ],
)
def test_redact(value, expected):
    assert redact(value) == expected


def test_thresholds_can_be_relaxed():
    ds = load_dataset([FIXTURES / "dirty.jsonl"])
    result = CHECKS_BY_ID["dup"].run(ds, ctx(dup__max_near_dup_pct=100.0))
    assert result.severity is Severity.OK

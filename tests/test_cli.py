import json
from pathlib import Path

from datasets_lint.checks import ALL_CHECKS
from datasets_lint.cli import main
from datasets_lint.config import Config
from datasets_lint.dataset import load_dataset
from datasets_lint.engine import build_report, run_checks
from datasets_lint.report.html_out import render_html

FIXTURES = Path(__file__).parent / "fixtures"
CLEAN = str(FIXTURES / "clean.jsonl")
DIRTY = str(FIXTURES / "dirty.jsonl")


def test_clean_exit_zero(capsys):
    assert main(["run", CLEAN]) == 0
    out = capsys.readouterr().out
    assert "verdict: ok" in out


def test_dirty_exit_one(capsys):
    assert main(["run", DIRTY]) == 1
    assert "verdict: error" in capsys.readouterr().out


def test_fail_on_none_never_fails(capsys):
    assert main(["run", DIRTY, "--fail-on", "none"]) == 0


def test_fail_on_warn(capsys):
    assert main(["run", DIRTY, "--fail-on", "warn"]) == 1


def test_json_report_is_written(tmp_path, capsys):
    out = tmp_path / "report.json"
    main(["run", DIRTY, "--json-out", str(out), "--quiet"])
    data = json.loads(out.read_text())
    assert data["tool"] == "datasets-lint"
    assert data["verdict"] == "error"
    assert {c["id"] for c in data["checks"]} == {"stats", "dup", "pii", "contamination"}


def test_html_report_is_written(tmp_path, capsys):
    out = tmp_path / "report.html"
    main(["run", DIRTY, "--report", str(out), "--quiet"])
    html = out.read_text()
    assert "<!doctype html>" in html
    assert "datasets-lint report" in html
    assert "jane.doe@example.com" not in html


def test_selecting_checks(capsys):
    main(["run", DIRTY, "--checks", "pii"])
    out = capsys.readouterr().out
    assert "pii" in out
    assert "dup" not in out


def test_unknown_check_is_usage_error(capsys):
    assert main(["run", CLEAN, "--checks", "nope"]) == 2
    assert "unknown check" in capsys.readouterr().err


def test_baseline_diff(tmp_path, capsys):
    first = tmp_path / "first.json"
    main(["run", DIRTY, "--json-out", str(first), "--quiet"])
    assert main(["run", CLEAN, "--baseline", str(first)]) == 0
    out = capsys.readouterr().out
    assert "vs baseline" in out
    assert "better" in out


def test_checks_command_lists_all(capsys):
    assert main(["checks"]) == 0
    out = capsys.readouterr().out
    for check_id in ("stats", "dup", "pii", "contamination"):
        assert check_id in out


def test_render_html_contains_sections():
    ds = load_dataset([DIRTY])
    cfg = Config()
    results = run_checks(ds, cfg, list(ALL_CHECKS))
    report = build_report(ds, cfg, results)
    html = render_html(report)
    assert "Duplicates" in html
    assert "PII &amp; secrets" in html
    assert "verdict: error" in html

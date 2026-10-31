"""Tests for the enterprise surface: schema, leakage, SARIF, profiles, suppressions."""

import json
from pathlib import Path

from datasets_lint.checks import Context, checks_by_id
from datasets_lint.cli import main
from datasets_lint.config import Config, Suppression, load_config
from datasets_lint.dataset import load_dataset
from datasets_lint.engine import build_report, resolve_checks, run_checks
from datasets_lint.report.sarif import to_sarif

FIXTURES = Path(__file__).parent / "fixtures"
CLEAN = str(FIXTURES / "clean.jsonl")
DIRTY = str(FIXTURES / "dirty.jsonl")


def ctx(**checks) -> Context:
    return Context(config=Config(checks=checks))


# --- schema ---------------------------------------------------------------


def test_schema_flags_missing_required_column():
    ds = load_dataset([CLEAN])
    result = checks_by_id()["schema"].run(ds, ctx(schema={"required": ["text", "nope"]}))
    assert result.metrics["missing_columns"] == ["nope"]
    assert result.severity.value == "error"


def test_schema_flags_type_errors():
    ds = load_dataset([CLEAN])
    result = checks_by_id()["schema"].run(ds, ctx(schema={"types": {"text": "integer"}}))
    assert result.metrics["type_errors"]["text"] == 10
    assert result.severity.value == "error"


def test_schema_rejects_unknown_declared_type():
    ds = load_dataset([CLEAN])
    result = checks_by_id()["schema"].run(ds, ctx(schema={"types": {"text": "uuid"}}))
    assert any("unknown type" in f.message for f in result.findings)


def test_schema_cardinality_is_a_warning():
    ds = load_dataset([CLEAN])
    result = checks_by_id()["schema"].run(ds, ctx(schema={"max_cardinality": {"label": 2}}))
    assert result.metrics["cardinality_violations"]["label"] == 5
    assert result.severity.value == "warn"


def test_schema_ok_by_default():
    ds = load_dataset([CLEAN])
    result = checks_by_id()["schema"].run(ds, ctx())
    assert result.severity.value == "ok"


# --- leakage --------------------------------------------------------------


def test_leakage_detects_conflicting_labels():
    ds = load_dataset([FIXTURES / "conflicts.jsonl"])
    result = checks_by_id()["leakage"].run(ds, ctx())
    assert result.metrics["conflict_groups"] == 1
    assert result.metrics["rows_in_conflict"] == 3
    assert result.severity.value == "error"


def test_leakage_skips_without_label_column():
    ds = load_dataset([CLEAN])
    ds.label_column = None
    result = checks_by_id()["leakage"].run(ds, ctx())
    assert result.severity.value == "ok"
    assert "skipped" in result.summary


# --- SARIF ----------------------------------------------------------------


def test_sarif_document_is_valid_shape():
    ds = load_dataset([DIRTY])
    cfg = Config()
    report = build_report(ds, cfg, run_checks(ds, cfg, resolve_checks(None, None)))
    sarif = to_sarif(report)
    assert sarif["version"] == "2.1.0"
    run = sarif["runs"][0]
    assert run["tool"]["driver"]["name"] == "datasets-lint"
    assert {r["id"] for r in run["tool"]["driver"]["rules"]} >= {"dup", "pii"}
    assert all("ruleId" in r and r["locations"] for r in run["results"])


def test_cli_writes_sarif(tmp_path):
    out = tmp_path / "report.sarif"
    main(["run", DIRTY, "--fail-on", "none", "--sarif", str(out), "--quiet"])
    data = json.loads(out.read_text())
    assert data["runs"][0]["properties"]["verdict"] == "error"


# --- profiles -------------------------------------------------------------


def test_profiles_change_fail_on(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["run", CLEAN, "--profile", "dev"]) == 0
    assert main(["run", DIRTY, "--profile", "ci"]) == 1
    assert main(["run", DIRTY, "--profile", "dev"]) == 0


def test_strict_profile_is_loaded(tmp_path):
    cfg_path = tmp_path / "datasets-lint.toml"
    cfg_path.write_text('[defaults]\nprofile = "strict"\n')
    cfg = load_config(cfg_path)
    assert cfg.profile == "strict"
    assert cfg.fail_on == "warn"
    assert cfg.threshold("dup", "max_near_dup_pct", 99) == 0.5


def test_unknown_profile_raises(tmp_path):
    cfg_path = tmp_path / "datasets-lint.toml"
    cfg_path.write_text('[defaults]\nprofile = "nope"\n')
    try:
        load_config(cfg_path)
    except ValueError as exc:
        assert "unknown profile" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


# --- suppressions ---------------------------------------------------------


def test_suppressed_rows_are_ignored_by_checks():
    ds = load_dataset([DIRTY])
    cfg = Config(suppressions=[Suppression(check="stats", rows=[7, 8], reason="known empties")])
    result = checks_by_id()["stats"].run(ds, Context(config=cfg))
    assert result.metrics["empty_rows"] == 0
    assert result.severity.value != "error"


def test_expired_suppressions_do_not_apply():
    from datetime import date

    ds = load_dataset([DIRTY])
    cfg = Config(
        suppressions=[
            Suppression(check="stats", rows=[7, 8], reason="old", expires=date(2000, 1, 1))
        ]
    )
    result = checks_by_id()["stats"].run(ds, Context(config=cfg))
    assert result.metrics["empty_rows"] == 2


def test_suppressions_appear_in_report(tmp_path):
    cfg_path = tmp_path / "datasets-lint.toml"
    cfg_path.write_text('[[suppress]]\ncheck = "stats"\nrows = [7, 8]\nreason = "known empties"\n')
    out = tmp_path / "report.json"
    main(
        [
            "run",
            DIRTY,
            "--config",
            str(cfg_path),
            "--fail-on",
            "none",
            "--json-out",
            str(out),
            "--quiet",
        ]
    )
    data = json.loads(out.read_text())
    assert data["suppressions"][0]["reason"] == "known empties"
    assert data["suppressions"][0]["rows"] == [7, 8]

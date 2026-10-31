import json
from pathlib import Path

from datasets_lint.checks import ALL_CHECKS
from datasets_lint.cli import main
from datasets_lint.config import Config, load_config
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
    assert {c["id"] for c in data["checks"]} == {
        "stats",
        "dup",
        "pii",
        "contamination",
        "schema",
        "leakage",
    }


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
    for check_id in ("stats", "dup", "pii", "contamination", "schema", "leakage"):
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


def test_init_config_round_trips(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data = tmp_path / "data.jsonl"
    data.write_text(
        "\n".join(
            json.dumps(row)
            for row in [
                {"text": "hello", "label": "a", 'quoted"column 😀\x7f': 1},
                {"text": "", "label": "b", 'quoted"column 😀\x7f': None},
            ]
        ),
        encoding="utf-8",
    )
    assert main(["init", str(data)]) == 0
    config = load_config()
    assert config.text_column == "text"
    assert config.label_column == "label"
    assert config.checks["schema"]["required"] == ["text", "label", 'quoted"column 😀\x7f']
    assert config.checks["stats"]["max_empty_pct"] == 51.0
    assert config.checks["stats"]["max_null_pct"] == 51.0
    assert config.checks["stats"]["min_label_pct"] == 49.0
    assert main(["run", str(data), "--checks", "stats,schema", "--no-plugins"]) == 0


def test_init_refuses_overwrite_unless_forced(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "datasets-lint.toml"
    config.write_text("# existing settings\n", encoding="utf-8")
    assert main(["init", CLEAN]) == 2
    assert config.read_text() == "# existing settings\n"
    assert "--force" in capsys.readouterr().err
    assert main(["init", CLEAN, "--force"]) == 0
    assert load_config().text_column == "text"


def test_init_missing_input_writes_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["init", "missing.jsonl"]) == 2
    assert not (tmp_path / "datasets-lint.toml").exists()
    assert "no such file" in capsys.readouterr().err


def test_init_numeric_dataset_omits_undetected_columns(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data = tmp_path / "data.csv"
    data.write_text("count\n1\n1\n", encoding="utf-8")
    assert main(["init", str(data)]) == 0
    config = load_config()
    assert config.text_column is None
    assert config.label_column is None
    assert config.checks["stats"]["max_empty_pct"] == 100.0


def test_init_empty_dataset_preserves_existing_config(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "empty.csv").write_text("text,label\n", encoding="utf-8")
    config = tmp_path / "datasets-lint.toml"
    config.write_text("# existing\n", encoding="utf-8")
    assert main(["init", "empty.csv", "--force"]) == 2
    assert config.read_text() == "# existing\n"
    assert "empty dataset" in capsys.readouterr().err

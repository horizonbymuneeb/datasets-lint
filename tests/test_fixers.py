import json
from pathlib import Path

import polars as pl

from datasets_lint.checks.base import Context
from datasets_lint.cli import main
from datasets_lint.config import Config
from datasets_lint.dataset import load_dataset
from datasets_lint.fixers import ALL_FIXERS, apply_fixes, plan_fixes, write_dataset

FIXTURES = Path(__file__).parent / "fixtures"
DIRTY = str(FIXTURES / "dirty.jsonl")


def ctx() -> Context:
    return Context(config=Config())


def test_plan_covers_every_fixer():
    assert set(ALL_FIXERS) == {"dup", "stats", "pii", "contamination"}


def test_plan_drops_duplicates_and_empties():
    ds = load_dataset([DIRTY])
    plan = plan_fixes(ds, ctx())
    assert len(plan.drop["dup"]) == 2  # two copies of the mitochondria row
    assert len(plan.drop["stats"]) == 2  # "" and "   "
    assert plan.dropped_rows == {1, 2, 7, 8}


def test_keep_last_keeps_the_other_copy():
    ds = load_dataset([DIRTY])
    first = plan_fixes(ds, ctx(), keep="first")
    last = plan_fixes(ds, ctx(), keep="last")
    assert first.drop["dup"] != last.drop["dup"]
    assert len(first.drop["dup"]) == len(last.drop["dup"]) == 2


def test_apply_redacts_pii_in_place():
    ds = load_dataset([DIRTY])
    outcome = apply_fixes(ds, plan_fixes(ds, ctx()))
    text = " ".join(str(r["text"]) for r in outcome.rows)
    assert "jane.doe@example.com" not in text
    assert "[REDACTED_EMAIL]" in text
    assert "[REDACTED_PHONE]" in text
    assert "[REDACTED_API_KEY]" in text
    assert outcome.stats["input_rows"] == 12
    assert outcome.stats["output_rows"] == 8
    assert outcome.stats["dropped_by_fixer"] == {"dup": 2, "stats": 2}
    assert outcome.stats["redactions"] == {"email": 1, "phone": 1, "api_key": 1}


def test_pii_drop_mode_removes_rows():
    ds = load_dataset([DIRTY])
    outcome = apply_fixes(ds, plan_fixes(ds, ctx(), pii_action="drop"))
    assert outcome.stats["dropped_by_fixer"]["pii"] == 3
    assert "[REDACTED" not in " ".join(str(r["text"]) for r in outcome.rows)


def test_fix_only_limits_the_plan():
    ds = load_dataset([DIRTY])
    plan = plan_fixes(ds, ctx(), only=["pii"])
    assert set(plan.drop) == set()
    assert len(plan.redact) == 3


def test_unknown_fixer_raises():
    ds = load_dataset([DIRTY])
    try:
        plan_fixes(ds, ctx(), only=["nope"])
    except ValueError as exc:
        assert "unknown fixer" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_drop_contaminated_is_opt_in(tmp_path):
    eval_path = tmp_path / "eval.jsonl"
    eval_path.write_text(
        json.dumps(
            {
                "text": "A train travels 120 kilometers in 2 hours. "
                "What is its average speed in kilometers per hour?"
            }
        )
        + "\n"
    )
    cfg = Config(
        checks={"contamination": {"eval_sets": [], "custom_eval_sets": {"mini": str(eval_path)}}}
    )
    ds = load_dataset([FIXTURES / "contaminated.jsonl"])
    context = Context(config=cfg)
    assert "contamination" not in plan_fixes(ds, context).drop
    plan = plan_fixes(ds, context, drop_contaminated=True)
    assert len(plan.drop["contamination"]) >= 1


def test_write_dataset_formats(tmp_path):
    rows = [{"text": "a", "label": "x"}, {"text": "b", "label": "y"}]
    jsonl = write_dataset(rows, tmp_path / "out.jsonl", ["text", "label"])
    assert len(jsonl.read_text().splitlines()) == 2

    csv = write_dataset(rows, tmp_path / "out.csv", ["text", "label"])
    assert pl.read_csv(csv).height == 2

    parquet = write_dataset(rows, tmp_path / "out.parquet", ["text", "label"])
    assert pl.read_parquet(parquet).height == 2

    as_json = write_dataset(rows, tmp_path / "out.json", ["text", "label"])
    assert json.loads(as_json.read_text())[0]["text"] == "a"


def test_cli_fix_writes_file_and_reports(tmp_path, capsys):
    out = tmp_path / "clean.jsonl"
    code = main(["run", DIRTY, "--fail-on", "none", "--fix", str(out)])
    assert code == 0
    assert out.exists()
    assert len(out.read_text().splitlines()) == 8
    printed = capsys.readouterr().out
    assert "fixes: 4 rows dropped" in printed
    assert "redactions" in printed


def test_cli_dry_run_writes_nothing(tmp_path, capsys):
    out = tmp_path / "clean.jsonl"
    assert main(["run", DIRTY, "--fail-on", "none", "--fix", str(out), "--dry-run"]) == 0
    assert not out.exists()
    assert "dry run" in capsys.readouterr().out


def test_cli_fix_is_in_json_report(tmp_path):
    report = tmp_path / "report.json"
    out = tmp_path / "clean.jsonl"
    main(
        ["run", DIRTY, "--fail-on", "none", "--fix", str(out), "--json-out", str(report), "--quiet"]
    )
    data = json.loads(report.read_text())
    assert data["fixes"]["output_rows"] == 8
    assert data["fixes"]["dropped_by_fixer"] == {"dup": 2, "stats": 2}

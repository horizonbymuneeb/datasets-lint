import json
from pathlib import Path

from datasets_lint.checks import CHECKS_BY_ID, Context
from datasets_lint.config import Config
from datasets_lint.dataset import load_dataset
from datasets_lint.eval_sets import available, eval_texts, load_eval_set, ngrams
from datasets_lint.result import Severity

FIXTURES = Path(__file__).parent / "fixtures"
EVAL_TEXT = (
    "A train travels 120 kilometers in 2 hours. What is its average speed in kilometers per hour?"
)


def ctx(**check_config) -> Context:
    return Context(config=Config(checks={"contamination": check_config}))


def mini_eval(tmp_path) -> str:
    path = tmp_path / "mini_eval.jsonl"
    path.write_text(json.dumps({"text": EVAL_TEXT}) + "\n")
    return str(path)


def test_detects_verbatim_and_embedded_eval_rows(tmp_path):
    ds = load_dataset([FIXTURES / "contaminated.jsonl"])
    result = CHECKS_BY_ID["contamination"].run(
        ds, ctx(eval_sets=[], custom_eval_sets={"mini": mini_eval(tmp_path)})
    )
    assert result.metrics["rows_contaminated"] == 2  # verbatim + embedded
    assert result.metrics["per_eval_set"]["mini"]["rows"] == 2
    assert result.metrics["per_eval_set"]["mini"]["max_containment"] == 1.0
    assert result.severity is Severity.ERROR
    assert all(f.detail["eval_set"] == "mini" for f in result.findings)


def test_clean_rows_are_not_flagged(tmp_path):
    ds = load_dataset([FIXTURES / "clean.jsonl"])
    result = CHECKS_BY_ID["contamination"].run(
        ds, ctx(eval_sets=[], custom_eval_sets={"mini": mini_eval(tmp_path)})
    )
    assert result.metrics["rows_contaminated"] == 0
    assert result.severity is Severity.OK


def test_bundled_gsm8k_row_is_caught(tmp_path):
    gsm_row = eval_texts("gsm8k")[0].split("\n")[0]
    data = tmp_path / "leak.jsonl"
    data.write_text(json.dumps({"text": gsm_row}) + "\n")
    ds = load_dataset([data])
    result = CHECKS_BY_ID["contamination"].run(ds, ctx(eval_sets=["gsm8k"]))
    assert result.metrics["rows_contaminated"] == 1
    assert result.metrics["per_eval_set"]["gsm8k"]["max_containment"] >= 0.5


def test_thresholds_can_be_relaxed(tmp_path):
    ds = load_dataset([FIXTURES / "contaminated.jsonl"])
    result = CHECKS_BY_ID["contamination"].run(
        ds,
        ctx(
            eval_sets=[],
            custom_eval_sets={"mini": mini_eval(tmp_path)},
            max_contaminated_pct=100.0,
            min_containment=0.99,
        ),
    )
    assert result.severity is Severity.WARN  # verbatim row remains, embedded does not


def test_bundled_sets_are_listed_and_loadable():
    names = available()
    assert {"gsm8k", "humaneval", "mmlu"} <= set(names)
    gsm = load_eval_set("gsm8k", 8)
    assert gsm.rows == 1319
    assert gsm.size > 10_000


def test_bundled_mmlu_row_is_caught(tmp_path):
    mmlu_row = eval_texts("mmlu")[0]
    data = tmp_path / "mmlu_leak.jsonl"
    data.write_text(json.dumps({"text": mmlu_row}) + "\n")
    ds = load_dataset([data])
    result = CHECKS_BY_ID["contamination"].run(ds, ctx(eval_sets=["mmlu"]))
    assert result.metrics["rows_contaminated"] == 1
    assert result.metrics["per_eval_set"]["mmlu"]["max_containment"] >= 0.9


def test_ngrams_short_text_is_empty():
    assert ngrams("too short", 8) == set()
    assert len(ngrams("one two three four five six seven eight", 8)) == 1

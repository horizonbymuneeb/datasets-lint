from pathlib import Path

import pytest

from datasets_lint.dataset import DatasetError, load_dataset, normalize

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_jsonl_infers_columns():
    ds = load_dataset([FIXTURES / "clean.jsonl"])
    assert ds.total_rows == 10
    assert ds.audited_rows == 10
    assert ds.text_column == "text"
    assert ds.label_column == "label"
    assert ds.rows[0]["text"].startswith("The mitochondria")


def test_sampling_is_seeded_and_capped():
    a = load_dataset([FIXTURES / "dirty.jsonl"], sample=4, seed=7)
    b = load_dataset([FIXTURES / "dirty.jsonl"], sample=4, seed=7)
    assert a.audited_rows == 4
    assert a.total_rows == 12
    assert [r["text"] for r in a.rows] == [r["text"] for r in b.rows]


def test_explicit_columns_are_respected():
    ds = load_dataset([FIXTURES / "clean.jsonl"], text_column="label", label_column="text")
    assert ds.text_column == "label"
    assert ds.label_column == "text"


def test_missing_explicit_column_raises():
    with pytest.raises(DatasetError, match="text column 'nope' not found"):
        load_dataset([FIXTURES / "clean.jsonl"], text_column="nope")


def test_unsupported_suffix_raises(tmp_path):
    bad = tmp_path / "data.txt"
    bad.write_text("hello")
    with pytest.raises(DatasetError, match="unsupported file type"):
        load_dataset([bad])


def test_missing_file_raises():
    with pytest.raises(DatasetError, match="no such file"):
        load_dataset(["does-not-exist.jsonl"])


def test_multiple_files_get_source_column(tmp_path):
    ds = load_dataset([FIXTURES / "clean.jsonl", FIXTURES / "dirty.jsonl"])
    assert len(ds.sources) == 2
    assert {r["__source"] for r in ds.rows} == {"clean.jsonl", "dirty.jsonl"}


def test_normalize_collapses_whitespace():
    assert normalize("  Hello   World\n") == "hello world"

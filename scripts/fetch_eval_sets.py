"""Fetch and normalize the bundled eval sets used by the `contamination` check.

    python scripts/fetch_eval_sets.py

Downloads the public eval sets, normalizes them to `{"id", "text"}` JSONL, gzips
them deterministically and writes a manifest with source URL, license and sha256.
Run this only when you want to refresh the bundled data; the result is committed.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "src" / "datasets_lint" / "data" / "eval"

SOURCES = {
    "gsm8k": {
        "url": "https://raw.githubusercontent.com/openai/grade-school-math/master/grade_school_math/data/test.jsonl",
        "source": "https://github.com/openai/grade-school-math",
        "license": "MIT",
        "description": "GSM8K test split — grade-school math word problems",
    },
    "humaneval": {
        "url": "https://raw.githubusercontent.com/openai/human-eval/master/data/HumanEval.jsonl.gz",
        "source": "https://github.com/openai/human-eval",
        "license": "MIT",
        "description": "HumanEval — Python function synthesis problems",
    },
    "mmlu": {
        "url": "https://huggingface.co/datasets/cais/mmlu/resolve/main/all/test-00000-of-00001.parquet",
        "source": "https://huggingface.co/datasets/cais/mmlu",
        "license": "MIT",
        "description": "MMLU test split — 57-subject multiple-choice knowledge benchmark",
        "format": "parquet",
    },
}


def _download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as resp:  # noqa: S310 - fixed https URLs
        return resp.read()


def _iter_rows(name: str, raw: bytes):
    if name == "mmlu":
        import io as _io

        import polars as pl

        frame = pl.read_parquet(_io.BytesIO(raw))
        for row in frame.iter_rows(named=True):
            choices = " ".join(str(c) for c in row["choices"])
            yield {
                "id": row.get("subject"),
                "text": f"{row['question']} {choices}",
            }
    elif name == "humaneval":
        text = gzip.decompress(raw).decode("utf-8")
        for line in text.splitlines():
            row = json.loads(line)
            yield {
                "id": row["task_id"],
                "text": row["prompt"] + "\n" + row.get("canonical_solution", ""),
            }
    else:
        for line in raw.decode("utf-8").splitlines():
            row = json.loads(line)
            yield {"id": None, "text": row["question"] + "\n" + row["answer"]}


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict] = {}

    for name, meta in SOURCES.items():
        raw = _download(meta["url"])
        rows = list(_iter_rows(name, raw))
        payload = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows).encode("utf-8")
        buf = io.BytesIO()
        # mtime=0 keeps the gzip byte-for-byte reproducible across runs
        with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
            gz.write(payload)
        blob = buf.getvalue()
        out = DATA / f"{name}.jsonl.gz"
        out.write_bytes(blob)
        manifest[name] = {
            **meta,
            "file": out.name,
            "rows": len(rows),
            "bytes": len(blob),
            "sha256": hashlib.sha256(blob).hexdigest(),
        }
        print(f"{name:10s} {len(rows):5d} rows  {len(blob) / 1024:7.1f} KB  -> {out}")

    (DATA / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"manifest -> {DATA / 'manifest.json'}")


if __name__ == "__main__":
    main()

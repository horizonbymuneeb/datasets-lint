"""Bundled eval sets and the n-gram fingerprints used to detect contamination.

A fingerprint is the set of 64-bit hashes of all word n-grams in an eval set.
A dataset row is "contaminated" when a large share of *its* n-grams appear in the
fingerprint — i.e. containment, not symmetric Jaccard, because a training row may
legitimately be much longer than the eval question it leaked.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import dataclass, field
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

from datasets_lint.dataset import Dataset, normalize

DATA_PKG = "datasets_lint"
DATA_SUBDIR = "data/eval"
MANIFEST = "manifest.json"


def _data_file(name: str):
    return files(DATA_PKG).joinpath(f"{DATA_SUBDIR}/{name}")


@lru_cache(maxsize=1)
def manifest() -> dict[str, dict]:
    raw = _data_file(MANIFEST).read_text(encoding="utf-8")
    return json.loads(raw)


def available() -> list[str]:
    return sorted(manifest())


def hash_ngram(text: str) -> int:
    return int.from_bytes(hashlib.blake2b(text.encode(), digest_size=8).digest(), "big")


def ngrams(text: str, size: int) -> set[int]:
    words = text.split()
    if len(words) < size:
        return set()
    return {hash_ngram(" ".join(words[i : i + size])) for i in range(len(words) - size + 1)}


@dataclass
class EvalSet:
    name: str
    rows: int
    grams: set[int] = field(default_factory=set)
    exact: set[int] = field(default_factory=set)
    source: str = ""

    @property
    def size(self) -> int:
        return len(self.grams)


def eval_texts(name: str) -> list[str]:
    """Raw texts of a bundled eval set (used by tests and `--list-eval-sets`)."""
    return _read_bundled(name)


def _read_bundled(name: str) -> list[str]:
    meta = manifest().get(name)
    if meta is None:
        raise KeyError(f"unknown eval set {name!r}; available: {', '.join(available())}")
    blob = gzip.decompress(_data_file(meta["file"]).read_bytes()).decode("utf-8")
    return [json.loads(line)["text"] for line in blob.splitlines() if line.strip()]


def _read_custom(path: str | Path) -> list[str]:
    path = Path(path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"custom eval set not found: {path}")
    if path.suffix == ".txt":
        return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    from datasets_lint.dataset import load_dataset

    ds: Dataset = load_dataset([path], sample=1_000_000)
    return [t for _, t in ds.texts() if t.strip()]


@lru_cache(maxsize=32)
def load_eval_set(name: str, ngram: int = 8, custom_path: str | None = None) -> EvalSet:
    if custom_path is not None:
        texts = _read_custom(custom_path)
        source = str(custom_path)
    else:
        texts = _read_bundled(name)
        source = manifest()[name]["source"]

    grams: set[int] = set()
    exact: set[int] = set()
    for text in texts:
        norm = normalize(text)
        exact.add(hash_ngram(norm))
        grams |= ngrams(norm, ngram)

    return EvalSet(name=name, rows=len(texts), grams=grams, exact=exact, source=source)

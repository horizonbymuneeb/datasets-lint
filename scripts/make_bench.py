"""Generate a synthetic benchmark dataset: 100k rows, ~5% duplicates, some PII.

    python scripts/make_bench.py /tmp/bench.jsonl --rows 100000

Used to check the "<60s for 100k rows" budget on a 4 vCPU / 8 GB box.
"""

from __future__ import annotations

import argparse
import json
import random

VOCAB = [f"token{i}" for i in range(3000)]
SENTENCE_TAILS = ["?", ".", "!", " — see docs.", " (beta)."]


def make_text(rng: random.Random, n_words: int) -> str:
    words = [rng.choice(VOCAB) for _ in range(n_words)]
    words[0] = words[0].capitalize()
    return " ".join(words) + rng.choice(SENTENCE_TAILS)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--rows", type=int, default=100_000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--dup-pct", type=float, default=5.0)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    n_dups = int(args.rows * args.dup_pct / 100)
    n_near = n_dups // 2
    n_unique = args.rows - n_dups
    rows = []
    for _ in range(n_unique):
        rows.append({"text": make_text(rng, rng.randint(30, 80)), "label": rng.choice("abcde")})
    for _ in range(n_near):  # near-duplicates: one word swapped
        src = rows[rng.randrange(n_unique)]
        words = src["text"].split()
        words[rng.randrange(len(words))] = rng.choice(VOCAB)
        rows.append({"text": " ".join(words), "label": src["label"]})
    for _ in range(n_dups - n_near):  # exact duplicates
        src = rows[rng.randrange(n_unique)]
        rows.append({"text": src["text"], "label": src["label"]})
    for i in range(0, n_unique, 5000):  # a few PII rows
        rows[i]["text"] += f" contact: user{i}@example.com"
    rng.shuffle(rows)

    with open(args.out, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    print(f"wrote {len(rows):,} rows to {args.out}")


if __name__ == "__main__":
    main()

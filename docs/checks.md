# Checks

Every check returns a severity (`ok`, `warn`, `error`), a one-line summary, numeric
metrics and up to 50 sampled findings. Metrics are stable keys — safe to graph.

## `stats` — distribution & shape

Rows, nulls per column, empty rows, text-length percentiles, label balance.

| metric | meaning |
|---|---|
| `rows` | rows audited after suppressions |
| `empty_rows`, `empty_pct` | rows whose text is empty or whitespace |
| `null_pct` | per-column null percentage |
| `text_len` | `p50`, `p95`, `max`, `mean` in characters |
| `n_unique_texts` | distinct normalized texts |
| `label_balance_pct` | label distribution, top 20 |

Fails when `empty_pct > max_empty_pct` (default 1%).

## `dup` — duplicates

Exact duplicates by hash, near-duplicates by MinHash/LSH with **exact Jaccard
verification** of every candidate pair (so short rows are not missed).

| metric | meaning |
|---|---|
| `exact_dup_pct` | rows in exact-duplicate groups |
| `near_dup_pct` | rows in near-duplicate clusters |
| `near_dup_clusters`, `largest_cluster` | cluster shape |
| `cross_source_dup_pct` | rows duplicated across input files (train/test leaks) |
| `candidate_pairs`, `verified_pairs` | LSH efficiency |

Fails when `near_dup_pct > max_near_dup_pct` (default 2%).

## `pii` — PII & secrets

| kind | severity | examples |
|---|---|---|
| `api_key`, `private_key`, `iban`, `ssn` | error | `sk-…`, `AKIA…`, `ghp_…` |
| `email`, `phone`, `ipv4` | warn | `a@b.com`, `555-867-5309`, `10.0.0.1` |

Findings are **redacted** (`j***@example.com`) — the report never contains the secret.
Arithmetic such as `180-135` inside math answers is not treated as a phone number.

## `contamination` — eval-set leakage

Bundled fingerprints: **GSM8K** (1,319 rows), **HumanEval** (164), **MMLU** (14,042). Containment
scoring: the share of a row's 8-grams that already exist in the eval set. A long
training row that embeds a benchmark question still scores ~1.0.

```toml
[checks.contamination]
eval_sets = ["gsm8k", "humaneval", "mmlu"]
ngram = 8
min_containment = 0.5
max_contaminated_pct = 1.0
```

## `schema` — columns, types, cardinality

```toml
[checks.schema]
required = ["text", "label"]
types = { label = "string" }
max_cardinality = { label = 50 }
```

Missing columns and type errors are `error`; cardinality overruns are `warn`.

## `leakage` — label conflicts

Identical (normalized) texts annotated with different labels: label noise, or a
train/test split that contradicts itself. Fails above `max_conflict_pct` (default 1%).

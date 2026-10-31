# Configuration

`datasets-lint` reads `datasets-lint.toml` from the working directory, or any path
given with `--config`. Every option has a safe default, so an empty config is valid.

```toml
[defaults]
profile = "default"      # default | strict | ci | dev
sample = 100000          # rows audited per run (seeded random sample)
seed = 0                 # sampling seed — same seed, same report
fail_on = "error"        # none | warn | error
text_column = "text"     # auto-detected when omitted
label_column = "label"   # auto-detected when omitted
plugins = true           # load third-party checks from entry points
```

## Generate a starting configuration

```console
datasets-lint init train.jsonl
```

This writes `datasets-lint.toml` in the current directory using the existing
text/label column inference, and makes the detected columns required. It uses the
standard deterministic sample (up to 100,000 rows, seed 0). Empty-text and
worst-column null percentages get one percentage point of headroom, capped at
100; the smallest label share reported by the stats check gets one percentage
point of tolerance, floored at zero. Comments record the sample size and margins.

Review the inferred columns and thresholds: this captures the current dataset's
baseline, not a guarantee that its quality is acceptable. Other checks retain
their defaults. Existing configuration is preserved unless you pass `--force`;
unreadable or empty datasets do not overwrite it.

## Profiles

A profile is a preset of thresholds; your `[checks.*]` values are merged on top.

| profile | fail_on | idea |
|---|---|---|
| `default` | `error` | normal local runs |
| `strict` | `warn` | publishing a dataset; near-dup > 0.5%, PII warnings fail |
| `ci` | `error` | pull requests |
| `dev` | `none` | never fails, always reports |

```console
$ datasets-lint run train.jsonl --profile strict
```

## Checks

```toml
[checks.stats]
max_empty_pct = 1.0
max_null_pct = 50.0
min_label_pct = 1.0

[checks.dup]
threshold = 0.7          # exact Jaccard cutoff, verified after LSH candidates
shingle_size = 3         # words per shingle
num_perm = 64            # MinHash permutations (candidate generation only)
max_chars = 300          # truncate each row before shingling
max_near_dup_pct = 2.0

[checks.pii]
max_error_findings_pct = 0.1   # secrets, IBANs, SSNs
max_warn_findings_pct = 5.0    # emails, phones, IPs

[checks.contamination]
eval_sets = ["gsm8k", "humaneval", "mmlu"]
ngram = 8
min_containment = 0.5
max_contaminated_pct = 1.0

[checks.contamination.custom_eval_sets]
my_bench = "evals/my_bench.jsonl"   # .jsonl | .json | .csv | .parquet | .txt

[checks.schema]
required = ["text", "label"]
types = { label = "string" }        # string | integer | float | boolean
max_cardinality = { label = 50 }

[checks.leakage]
max_conflict_pct = 1.0
```

## Suppressions

Suppressions are **auditable**: they need a reason and can expire. An expired
suppression silently stops applying, so exceptions do not live forever.

```toml
[[suppress]]
check = "pii"          # or "*" for every check
rows = [12, 13, 4012]
reason = "public support addresses, approved in DATA-118"
expires = "2027-01-01" # optional
```

Suppressed rows are excluded from that check's metrics and findings, and listed in
the JSON/HTML report under `suppressions`.

## Environment

| variable | effect |
|---|---|
| `NO_COLOR` | disable ANSI output |
| `DATASETS_LINT_CONFIG` | default config path when `--config` is not given |

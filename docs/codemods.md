# Codemods (`--fix`)

`--fix` writes a repaired copy of the dataset. It never mutates the input, and every
change is counted and sampled in the report.

```console
$ datasets-lint run train.jsonl --fix train.clean.jsonl
  ...
  fixes: 327 rows dropped (dup 326 · stats 1) · 26 redactions (email 13 · phone 13)
  fixed → train.clean.jsonl
```

| flag | meaning |
|---|---|
| `--fix OUT` | write the repaired dataset (`.jsonl`, `.json`, `.csv`, `.parquet`) |
| `--fix-only dup,pii` | run a subset of fixers |
| `--fix-keep first\|last` | which row of a duplicate cluster to keep |
| `--fix-pii redact\|drop` | redact PII in place (default) or drop those rows |
| `--fix-drop-contaminated` | also drop rows overlapping an eval set (opt-in) |
| `--dry-run` | plan and report, write nothing |

## Fixers

| fixer | action | safe by default |
|---|---|---|
| `dup` | drop all but one row per near-duplicate cluster | yes |
| `stats` | drop empty / whitespace-only rows | yes |
| `pii` | redact `[REDACTED_EMAIL]`, `[REDACTED_PHONE]`, `[REDACTED_API_KEY]`, … | yes |
| `contamination` | drop rows that overlap an eval set | **no** — opt-in only |

Order matters: plans are computed on the original rows, then applied
`dup → stats → pii → contamination`, so redaction never changes duplicate detection.

## Recipes

**Publish a clean dataset**

```console
datasets-lint run raw.jsonl --profile strict --fix public.jsonl --report audit.html
```

**Redact before shipping to a vendor**

```console
datasets-lint run export.jsonl --fix-only pii --fix-pii redact --fix vendor.jsonl
```

**Drop benchmark leaks**

```console
datasets-lint run train.jsonl --fix-only contamination --fix-drop-contaminated --fix train.noleak.jsonl
```

**See the impact of a rule change without touching data**

```console
datasets-lint run train.jsonl --fix /tmp/unused.jsonl --dry-run
```

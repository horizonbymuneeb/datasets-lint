# datasets-lint

**ruff for training data.** Audit a dataset for duplicates, PII, distribution problems
and eval-set contamination — offline, on CPU, in one command, with a CI-friendly exit code.

![report](report.png)

```console
$ uvx datasets-lint run train.jsonl --report out.html
  ✓ stats           120,000 rows · 0.00% empty
  ✗ dup             18.20% near-duplicate (4,211 clusters), 12.00% exact
  ✗ pii             0.41% of rows contain PII (email 487, phone 12, api_key 1)
  ✗ contamination   3.10% of rows overlap an eval set (gsm8k 3.10%)
  ✓ schema          schema ok (2 columns)
  ✓ leakage         no label conflicts

  verdict: error — 3 errors, 0 warnings, 3 ok · 13.43s
  report → out.html
```

## Quick start

```console
uvx datasets-lint run data.jsonl                          # audit
uvx datasets-lint run data.jsonl --profile strict          # publishing thresholds
uvx datasets-lint run data.jsonl --fix data.clean.jsonl    # codemod
uvx datasets-lint run data.jsonl --sarif out.sarif         # GitHub code scanning
```

## Why

- **fast** — 100k rows in ~46 s on 4 vCPU, 1.4 GB RAM, no GPU
- **offline** — no API keys, no cloud, nothing leaves the machine
- **CI-native** — exit codes, SARIF, JSON, `--baseline` diffs
- **actionable** — `--fix` writes a repaired dataset with an audit trail
- **extensible** — one check = one file, or a plugin package via entry points

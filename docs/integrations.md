# CI & integrations

## Exit codes

| code | meaning |
|---|---|
| `0` | ok (or `--fail-on none`) |
| `1` | a check reached the failure severity |
| `2` | usage or input error |

## GitHub Actions

```yaml
- uses: horizonbymuneeb/datasets-lint@v1
  with:
    paths: data/train.jsonl data/test.jsonl
    fail-on: error
    report: datasets-lint-report.html
- uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: datasets-lint.sarif
```

Or call the CLI directly, with SARIF for code scanning:

```yaml
- run: uvx datasets-lint run data/train.jsonl --sarif datasets-lint.sarif --report report.html
- uses: github/codeql-action/upload-sarif@v3
  if: always()
  with:
    sarif_file: datasets-lint.sarif
```

## pre-commit

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/horizonbymuneeb/datasets-lint
    rev: v1.0.0
    hooks:
      - id: datasets-lint
```

## Docker

```console
$ docker run --rm -v "$PWD:/data" ghcr.io/horizonbymuneeb/datasets-lint run /data/train.jsonl
```

## Baseline diffing

Fail a PR only when the data gets *worse*:

```console
datasets-lint run data.jsonl --json-out new.json
datasets-lint run data.jsonl --baseline main.json
```

```
  vs baseline:
    dup.near_dup_pct: 18.200 → 12.000 (-6.200) better
    pii.rows_with_pii_pct: 0.410 → 0.520 (+0.110) worse
```

## Programmatic API

```python
from datasets_lint import audit, Config

report = audit("train.jsonl", config=Config(profile="strict"))
if report.worst.value == "error":
    raise SystemExit(1)
for result in report.results:
    print(result.check_id, result.severity.value, result.summary)
```

# v1.0 — enterprise plan

**Status: shipped in v1.0.0.**

Goal: a tool a platform team can drop into a production data pipeline on day one:
**audit → auto-fix → gate CI → ship**, with no surprises.

## Pillars

| # | Pillar | What ships |
|---|---|---|
| 1 | **Codemods (`--fix`)** | deterministic dataset repairs: dedupe, drop empties, redact PII, drop contaminated rows; dry-run, per-fixer selection, audit trail |
| 2 | **Checks** | `stats`, `dup`, `pii`, `contamination`, `schema`, `leakage` (v1.0) |
| 3 | **Enterprise config** | profiles (`strict`/`ci`/`dev`), suppressions with justification + expiry, config schema validation |
| 4 | **Machine output** | JSON (stable), **SARIF 2.1.0** for GitHub code scanning, HTML, JUnit-ish exit codes |
| 5 | **Integrations** | GitHub Action with PR comment, pre-commit, Docker image, programmatic API, third-party checks via entry points |
| 6 | **Hardening** | mypy strict, coverage gate ≥85%, fuzz-ish property tests, deterministic runs, memory ceiling |
| 7 | **Docs** | mkdocs site, check reference, cookbook, ADRs, SECURITY.md, CODE_OF_CONDUCT.md |

## Non-negotiables

- **Deterministic**: same input + config + seed ⇒ byte-identical JSON report.
- **Bounded**: every check has a row cap, finding cap and time budget.
- **Offline**: no network at run time (except optional HF input).
- **Reversible**: `--fix` always writes a new file; never mutates the input.
- **Auditable**: every dropped/redacted row is counted and sampled in the report.

## API surface (frozen at 1.0)

```python
from datasets_lint import audit, fix, load_dataset, Config

report = audit("train.jsonl", config=Config(profile="strict"))
if report.worst == "error":
    ...
fixed = fix("train.jsonl", out="train.clean.jsonl", only=["dup", "pii"])
```

## Milestones

- **0.3** codemods + `schema` + `leakage` + SARIF
- **0.4** profiles, suppressions, entry-point plugins, Docker, docs site
- **1.0** mypy strict, coverage gate, API freeze, benchmarks in CI

# Contributing

Thanks for helping! This project is built to be contributed to: every check is a
single small file, and the plugin API is intentionally tiny.

## Setup

```console
git clone https://github.com/horizonbymuneeb/datasets-lint
cd datasets-lint
uv venv && uv pip install -e ".[dev]"
pytest
ruff check . && ruff format .
```

No GPU, no API keys, no network needed for tests.

## Add a check (the main way to contribute)

1. Copy an existing check, e.g. `src/datasets_lint/checks/stats.py`.
2. Implement `run(self, ds: Dataset, ctx: Context) -> CheckResult`.
   - read data via `ds.texts()` or `ds.rows` (already sampled)
   - read thresholds via `ctx.threshold(self.id, "name", default)`
   - return `severity`, a one-line `summary`, numeric `metrics`, and up to ~50 `Finding`s
   - **never** put raw PII in `message` — use `datasets_lint.checks.pii.redact`
3. Register it in `src/datasets_lint/checks/__init__.py`.
4. Add a tiny fixture under `tests/fixtures/` and a test in `tests/test_checks.py`.
5. Document the id, what it finds and its default threshold in `README.md`.

That's it — a reviewable PR of ~100 lines.

## Check design rules

- **Deterministic**: seed everything; the same input must give the same report.
- **Bounded**: cap findings and any quadratic work; sample if needed.
- **Fast**: a check should stay under ~10 s for 100k rows on 4 vCPUs.
- **Honest**: if a metric is an estimate, say so in the `summary` or `metrics` key name.
- **Actionable**: the finding message should tell the user what to do, not just what is wrong.

## Ideas that are not built yet

`contamination`, `leakage`, `langid`, `schema`, `toxicity`, `dedup-apply`,
SARIF output, HuggingFace Hub input (`hf:org/name`), WASM playground.
Open an issue before starting a big one so we don't duplicate work.

## Commit style

`check(dup): report cross-split clusters` — conventional-ish, no ceremony.

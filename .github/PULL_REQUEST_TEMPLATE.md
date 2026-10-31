## What does this PR do?

<!-- one paragraph -->

## Checklist

- [ ] `ruff check . && ruff format --check .` passes
- [ ] `mypy` passes
- [ ] `pytest` passes and coverage stays ≥ 80%
- [ ] New check: added to `checks/__init__.py`, with a fixture and a test
- [ ] New flag/config option: documented in `docs/`
- [ ] No raw PII in `Finding.message` (use `redact`)
- [ ] Deterministic: same input + seed ⇒ same report

## Related issue

<!-- fixes #123 -->

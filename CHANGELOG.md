# Changelog

## v0.2.0 — 2026-10-31

### Added
- **`contamination` check** — detects rows that leak public benchmarks.
  - bundled, offline fingerprints for **GSM8K** (1,319 rows) and **HumanEval** (164)
  - containment scoring (share of a row's n-grams found in the eval set), so a long
    training row that embeds a benchmark question is still caught
  - custom eval sets via `[checks.contamination.custom_eval_sets]`
  - `scripts/fetch_eval_sets.py` regenerates the bundled data with checksums

### Fixed
- `pii`: phone numbers were not matched in `3-3-4` form (`555-867-5309`) and arithmetic
  like `180-135` inside math answers was reported as a phone number. Both fixed, with
  tests for `555-867-5309`, `+1 415 555 1234`, `(415) 555-1234`, `180-135`, `2021-05-03`.

### Performance (4 vCPU, 8 GB, no GPU)
| dataset | wall | peak RSS |
|---|---|---|
| 100k rows, 54 MB JSONL, all 4 checks | 46 s | 1.4 GB |

## v0.1.0 — 2026-10-31

First release: `stats`, `dup`, `pii` checks, HTML + JSON reports, `--baseline` diffing,
GitHub Action, pre-commit hook, PyPI trusted publishing.

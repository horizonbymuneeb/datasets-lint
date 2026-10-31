# Changelog

## v1.1.0 — 2026-10-31

### Added
- **MMLU fingerprints** (14,042 test rows) in the `contamination` check — the default
  eval set list is now `["gsm8k", "humaneval", "mmlu"]`.
- `CODE_OF_CONDUCT.md`, `SECURITY.md`, issue forms, PR template.
- Launch kit (`docs/launch/launch-kit.md`) and eight `good first issue`s.

### Fixed
- Bundled JSONL parsing split on Unicode line separators (`\u2028`, `\x85`), which
  truncated MMLU rows; now splits on `\n` only.

### Numbers
| workload | wall | peak RSS |
|---|---|---|
| 100k rows, all six checks, 3 eval sets | 48 s | 1.4 GB |

## v1.0.0 — 2026-10-31

The enterprise release: audit → fix → gate CI → ship.

### Added
- **Codemods (`--fix`)** — deterministic dataset repairs with an audit trail:
  `dup` (drop duplicate clusters), `stats` (drop empty rows), `pii` (redact or drop),
  `contamination` (drop leaks, opt-in). `--fix-only`, `--fix-keep`, `--dry-run`,
  writes `.jsonl` / `.json` / `.csv` / `.parquet`.
- **Two new checks** — `schema` (required columns, types, cardinality) and
  `leakage` (identical texts with conflicting labels).
- **Profiles** — `default`, `strict`, `ci`, `dev` threshold presets.
- **Suppressions** — auditable, expiring, per-check row exceptions; listed in the report.
- **SARIF 2.1.0** output (`--sarif`) for GitHub code scanning.
- **Third-party checks** via `datasets_lint.checks` entry points (`--no-plugins` to disable).
- **Programmatic API** — `audit()`, `fix()`, `Config`, typed and stable.
- **Docs site** (mkdocs), `Dockerfile`, py.typed marker, mypy clean, coverage gate.

### Changed
- `resolve_checks()` accepts `include_plugins`; the CLI gained `--profile`, `--sarif`,
  `--no-plugins`, `--fix*` flags.
- The HTML report shows codemod results and suppressions.

### Fixed
- `pii`: 3-3-4 phone numbers were missed; arithmetic (`180-135`) was reported as a phone.

### Numbers (4 vCPU, 8 GB, no GPU)
| workload | wall | peak RSS |
|---|---|---|
| 100k rows, all checks | 46 s | 1.4 GB |
| 100k rows, all checks + `--fix` | 48 s | 1.5 GB |

## v0.2.0 — 2026-10-31

- **`contamination` check** with bundled GSM8K (1,319 rows) and HumanEval (164)
  fingerprints, containment scoring, and custom eval sets.
- `pii` phone-regex fixes with tests.

## v0.1.0 — 2026-10-31

First release: `stats`, `dup`, `pii`, HTML + JSON reports, `--baseline` diffing,
GitHub Action, pre-commit hook, PyPI trusted publishing.

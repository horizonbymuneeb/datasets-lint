# datasets-lint — Roadmap & Build Plan

> `ruff` for training data. A fast, CI-friendly linter that audits a dataset for
> duplicates, PII, label leakage, contamination and distribution problems, then
> emits a JSON + HTML report and a non-zero exit code when thresholds are breached.

**Status:** v0.1 core built — contamination + launch pending · **License:** MIT · **Stack:** Python 3.10+ (uv, polars, datasketch, jinja2)

---

## 1. Problem

Before fine-tuning or publishing a dataset, people hand-roll the same checks in
throwaway notebooks:

- exact/near-duplicate rows (inflate loss, leak eval answers)
- PII (emails, phones, keys) that must not ship
- train/test contamination against MMLU / GSM8K / HumanEval
- label leakage (target encoded in a feature)
- class imbalance, length outliers, empty/near-empty rows

Nothing packaged, nothing CI-able, nothing that produces a report a reviewer can read.
`datasets-lint` is that tool.

## 2. Non-goals (v0.1)

- No model training, no GPU, no LLM judges (must run offline on a laptop)
- No dataset hosting/versioning (we read local files + HF `datasets`)
- No automatic "fixing" of data — we report, the user decides
- No web UI/server in v1 (static HTML report only)

## 3. Success criteria

| Metric | Target |
|---|---|
| 100k-row JSONL audit (4 vCPU) | < 60 s, < 2 GB RSS |
| Checks shipped in v0.1 | 4 (`stats`, `dup`, `pii`, `contamination`) |
| Test coverage of core | ≥ 85% |
| Contributor on-ramp | one new check = one file + one fixture |
| Install | `uvx datasets-lint` works with zero config |

---

## 4. Phases

### Phase 0 — Skeleton (½ day)
- [x] Repo init, MIT license, `.gitignore`, README with the one-command demo
- [x] `pyproject.toml` (hatchling, src-layout, `console_scripts: datasets-lint`)
- [x] `uv sync`, ruff + pytest config
- **Exit:** `uv run datasets-lint --help` prints help.

### Phase 1 — Core engine (1 day)
- [x] `Dataset` loader: `.jsonl`, `.csv`, `.parquet` (HF `datasets` input is backlog)
- [x] Plugin API:
      `class Check(Protocol): id, name, run(ds, ctx) -> CheckResult`
- [x] `CheckResult` = severity, summary, metrics dict, findings (capped sample)
- [x] Registry + config file `datasets-lint.toml` (thresholds, ignore rules)
- [x] CLI: `datasets-lint run PATH [--checks ...] [--sample N] [--fail-on error]`
- **Exit:** two dummy checks run end-to-end and print a text summary.

### Phase 2 — First real checks (2–3 days)
- [x] `stats`: row count, nulls, token-length histogram, class balance, empty rows
- [x] `dup`: exact hash + MinHash/LSH near-dup, cluster report, % duplicated
- [x] `pii`: regex pack (email, phone, IBAN, IP, API-key shapes) + optional
      small NER via `[ner]` extra; findings redacted in report
- **Exit:** on a 50k sample of a public dataset, `dup` and `pii` produce
  plausible numbers in < 30 s.

### Phase 3 — Differentiator: contamination (2 days)
- [ ] Bundled mini eval-set fingerprints (GSM8K, MMLU sample, HumanEval) as n-gram
      sketches, downloaded on demand and cached
- [ ] `contamination`: n-gram overlap + MinHash match, per-eval-set hit rate
- [ ] Clear verdict: "3.1% of rows overlap GSM8K (threshold 1%)"
- **Exit:** a known-contaminated public dataset is correctly flagged; a clean one is not.

### Phase 4 — Reports (1–2 days)
- [x] JSON schema (stable, versioned) for machine consumption
- [x] HTML report via jinja2: summary cards, per-check sections, sample findings,
      histogram charts (inline SVG, no JS deps)
- [x] `--report out.html`, `--format json|text|html`
- [x] `--baseline prev.json` diff mode (did this PR make the data worse?)
- **Exit:** report opens standalone, looks good, includes exit-code rationale.

### Phase 5 — Packaging & distribution (1 day)
- [x] `uv build` → sdist + wheel; install into a clean venv and run the CLI
- [x] Extras: `[ner]`, `[hf]`, `[dev]`
- [ ] TestPyPI dry run → PyPI publish (Trusted Publishing via GitHub OIDC on tag)
- [ ] GitHub Action (`action.yml`): runs the linter, uploads report as artifact,
      posts a PR comment
- [ ] pre-commit hook definition
- **Exit:** `uvx datasets-lint run x.jsonl` works from a clean machine.

### Phase 6 — Launch (1 day)
- [ ] README: problem → 30-second demo → GIF of the HTML report → install → checks table
- [ ] `CONTRIBUTING.md` + `docs/writing-a-check.md` (10-line check example)
- [ ] 5–8 `good first issue` entries (one per missing check)
- [ ] CI matrix: Python 3.10–3.13, ruff, pytest, self-lint a fixture dataset
- [ ] Show HN / r/MachineLearning / HF forum post draft with real numbers
- **Exit:** a stranger can add a check in < 30 minutes using only the docs.

---

## 5. Repo layout

```
datasets-lint/
├── pyproject.toml
├── README.md  ROADMAP.md  CONTRIBUTING.md  LICENSE
├── action.yml                      # GitHub Action
├── .pre-commit-hooks.yaml
├── src/datasets_lint/
│   ├── cli.py
│   ├── dataset.py                  # loaders + sampling
│   ├── config.py                   # datasets-lint.toml
│   ├── registry.py                 # plugin discovery
│   ├── result.py                   # CheckResult, Severity, Report
│   ├── checks/{stats,dup,pii,contamination}.py
│   └── report/{json_out.py,html_out.py,templates/report.html.j2}
├── tests/{test_cli.py,test_checks/,fixtures/*.jsonl}
└── .github/workflows/{ci.yml,publish.yml}
```

## 6. Key design decisions

| Decision | Choice | Why |
|---|---|---|
| Data engine | `polars` (+ `pyarrow`) | fast on CPU, low RAM, lazy scans |
| Near-dup | `datasketch` MinHashLSH | battle-tested, tunable threshold |
| Sampling | default cap 100k rows, seeded | keeps CI fast and deterministic |
| Plugin model | plain Python protocol + registry | no entrypoint magic needed for v1 |
| Reports | jinja2 + inline SVG | single-file, no CDN, offline |
| Findings cap | 50 samples per check in report | avoid 500 MB HTML files |
| Exit codes | 0 ok, 1 threshold breach, 2 usage error | CI-friendly |

## 7. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Near-dup too slow on big files | sampling + LSH band tuning; `--sample` flag; benchmark in CI |
| Eval-set fingerprints are large | store 5-gram sketches, not text; lazy download + cache |
| PII regex false positives | severity `warn` by default, `error` only for high-confidence patterns |
| Scope creep (10 checks) | v0.1 ships 4; everything else is a `good first issue` |
| Name collision later | `datasets-lint` verified free on PyPI (2026-10-31) |

## 8. Day-by-day (compressed)

| Day | Deliverable |
|---|---|
| 1 | Phase 0 + Phase 1: skeleton, loader, plugin API, CLI |
| 2 | `stats` + `dup` working, tests |
| 3 | `pii`, config file, sampling, benchmarks |
| 4–5 | `contamination` + eval-set fingerprints |
| 6 | HTML/JSON reports + baseline diff |
| 7 | Packaging, TestPyPI, GitHub Action, pre-commit |
| 8 | Docs, launch README, good-first-issues, publish v0.1.0 |

## 9. Backlog after v0.1

`leakage` (target in features) · `dedup-apply` (emit cleaned file) · `langid` mix check ·
`toxicity` (small model) · `schema` check · SARIF output for GitHub code scanning ·
HF Hub integration (`datasets-lint run hf:org/name`) · Rust/`polars` fast path ·
web playground (WASM) · leaderboard of "lint scores" for popular public datasets.

---

## 10. Definition of done for v0.1.0

1. `uvx datasets-lint run data.jsonl --report out.html` works on a clean machine
2. 4 checks, documented, each with tests and a fixture
3. HTML + JSON report, exit codes correct
4. Published on PyPI, tag `v0.1.0`, GitHub Action usable
5. README has real benchmark numbers from this VM (4 vCPU / 8 GB)
6. ≥ 5 `good first issue`s open

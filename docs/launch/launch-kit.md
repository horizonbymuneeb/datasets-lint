# Launch kit

Three posts, one message: **you cannot trust a dataset you have not audited, and
auditing it should take one command.**

The hook that works: *"3.1% of your training rows are GSM8K answers"* — a number
people can check against their own data in under a minute.

---

## Hacker News

**Title:** Show HN: datasets-lint – audit a dataset for duplicates, PII and benchmark leaks

I kept re-writing the same dataset checks in throwaway notebooks: exact and near
duplicates, PII, label conflicts, and — the one that actually bites — contamination
against the eval set you are about to report numbers on.

So I packaged them: `datasets-lint` runs six checks offline on CPU, prints a verdict,
exits non-zero for CI, and writes a single-file HTML report. It also has `--fix`,
which writes a repaired copy (dedupe, drop empties, redact PII) with an audit trail.

```
$ uvx datasets-lint run train.jsonl --report out.html
  ✓ stats           120,000 rows · 0.00% empty
  ✗ dup             18.20% near-duplicate (4,211 clusters), 12.00% exact
  ✗ pii             0.41% of rows contain PII (email 487, phone 12, api_key 1)
  ✗ contamination   3.10% of rows overlap an eval set (gsm8k 3.10%)
```

Design decisions worth arguing about:

- **MinHash generates candidates, exact Jaccard decides.** A 64-permutation sketch
  on short instruction rows estimates 0.71 as 0.66 and misses obvious duplicates.
- **Contamination is containment, not Jaccard.** A long training row that embeds a
  benchmark question should still score 1.0.
- **Fingerprints ship with the package** (GSM8K, HumanEval, MMLU; MIT; checksummed),
  so it runs offline and reports are reproducible.
- **`--fix` never mutates the input** and counts every dropped/redacted row.

Numbers on a 4 vCPU / 8 GB box: 100k rows, 54 MB JSONL, all six checks in 48 s at
1.4 GB peak. 92% test coverage, mypy clean.

What I would like feedback on: which check is missing for your pipeline, and whether
the containment thresholds are sane on real corpora.

https://github.com/horizonbymuneeb/datasets-lint

---

## r/MachineLearning

**Title:** [P] datasets-lint: open-source audit for training data (duplicates, PII, benchmark contamination)

Fine-tuning or publishing a dataset usually means re-writing the same checks in a
notebook. I turned them into a CLI: six checks, one command, offline, CI-friendly.

The one I care about most is **contamination**: bundled fingerprints for GSM8K,
HumanEval and MMLU, scored by *containment* — the share of a row's n-grams that
already exist in the eval set — so a long row that swallowed a benchmark question
still gets flagged at ~100%.

```
$ datasets-lint run train.jsonl --report out.html
  ✗ contamination   3.10% of rows overlap an eval set (gsm8k 3.10%)
```

Also: exact+near duplicates with exact-Jaccard verification, redacted PII findings
(secrets fail CI, contact data warns), label-conflict detection, schema checks, and
`--fix` to write a cleaned copy with an audit trail.

No GPU, no API keys, nothing leaves the machine. 100k rows ≈ 48 s on 4 vCPU.
MIT licensed, plugins welcome (one check = one file).

Repo: https://github.com/horizonbymuneeb/datasets-lint
Happy to run it on a dataset you suspect is contaminated — drop a link.

---

## Hugging Face forum

**Title:** Auditing a dataset before you publish: duplicates, PII, and benchmark leakage

If you are about to publish or fine-tune on a dataset, three things bite later:

1. **Duplicates** — inflated metrics, memorisation, useless epochs.
2. **PII** — emails/phones/keys that should never have shipped.
3. **Contamination** — rows that overlap GSM8K/MMLU/HumanEval, which quietly
   invalidate every benchmark number you report afterwards.

`datasets-lint` checks all three (plus label conflicts and schema) in one command,
offline, and writes an HTML report you can attach to the dataset card:

```
$ uvx datasets-lint run train.jsonl --report audit.html
  ✓ stats · ✗ dup 18.2% · ✗ pii 0.41% · ✗ contamination 3.1% (gsm8k)
```

For dataset cards, the useful line is: *"audited with datasets-lint: 0 cross-split
duplicates, 0.0% PII, 0.0% eval-set overlap."* It is a claim a reviewer can re-run.

Feedback very welcome, especially on thresholds for non-English corpora.

---

## Launch checklist

- [x] PyPI package (trusted publishing)
- [x] README with screenshot + numbers
- [x] CI green on 3.10–3.13
- [x] `good first issue`s filed
- [x] Action published to the GitHub Marketplace
- [ ] Post to HN (Tue–Thu, 08:00–10:00 ET)
- [ ] Cross-post r/MachineLearning + HF forum same day
- [ ] Reply to every comment for the first 4 hours
- [ ] Tag `v1.0.1` with any fixes from day-one feedback

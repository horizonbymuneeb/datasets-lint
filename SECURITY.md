# Security policy

## Reporting a vulnerability

Please **do not** open a public issue for security problems. Use GitHub's private
vulnerability reporting: *Security → Report a vulnerability* on this repository.

We aim to acknowledge reports within 72 hours and ship a fix within 14 days for
confirmed issues.

## Scope

`datasets-lint` runs entirely locally and never sends data anywhere. The security
surface is therefore:

- **Parsing untrusted dataset files** (`.jsonl`, `.csv`, `.parquet`) — malformed
  input must never lead to code execution; report parser crashes as bugs.
- **Regex denial of service** — a pathological input causing the PII patterns to
  hang is a security issue; report it with the input that triggers it.
- **Report output** — HTML reports escape all dataset-derived strings. If you can
  get script execution into a report, that is a vulnerability.
- **Bundled eval data** — checksums are pinned in
  `src/datasets_lint/data/eval/manifest.json`; a mismatch is a supply-chain issue.

## Supported versions

The latest minor release receives security fixes.

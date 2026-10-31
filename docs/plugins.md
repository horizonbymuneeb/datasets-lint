# Plugins

Third-party checks are ordinary Python packages that expose a `datasets_lint.checks`
entry point.

```toml
# mycompany-lint/pyproject.toml
[project]
name = "mycompany-lint"
dependencies = ["datasets-lint>=1.0"]

[project.entry-points."datasets_lint.checks"]
internal_policy = "mycompany_lint:InternalPolicyCheck"
```

```python
# mycompany_lint/__init__.py
from datasets_lint.checks.base import Check, Context
from datasets_lint.dataset import Dataset
from datasets_lint.result import CheckResult, Finding, Severity


class InternalPolicyCheck(Check):
    id = "policy"
    title = "Internal data policy"
    description = "Rejects rows that mention internal project codenames."

    def run(self, ds: Dataset, ctx: Context) -> CheckResult:
        banned = ctx.threshold(self.id, "banned_terms", ["project-x"])
        hits = [
            Finding(message=f"banned term {term!r}", row=i)
            for i, text in ds.texts()
            for term in banned
            if term in text.lower() and not ctx.is_suppressed(self.id, i)
        ]
        return CheckResult(
            check_id=self.id,
            title=self.title,
            severity=Severity.ERROR if hits else Severity.OK,
            summary=f"{len(hits)} rows violate policy",
            metrics={"violations": len(hits)},
            findings=hits[:50],
        )
```

Install it next to `datasets-lint` (`pip install mycompany-lint`) and it appears
automatically:

```console
$ datasets-lint checks
  policy    Internal data policy
$ datasets-lint run data.jsonl --checks policy
```

Disable all plugins for a run with `--no-plugins` or `plugins = false` in the config.

## Rules for plugin authors

- Deterministic: seed anything random from `ctx.seed`.
- Bounded: cap findings at ~50 and avoid quadratic scans.
- Redact: never put raw PII in `Finding.message`.
- Respect suppressions: skip rows where `ctx.is_suppressed(self.id, row)`.
- Declare a stable `id` — it is the config key and the SARIF rule id.

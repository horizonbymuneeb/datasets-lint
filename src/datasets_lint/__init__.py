"""datasets-lint — ruff for training data.

Audit a dataset for duplicates, PII, distribution problems and eval-set
contamination. Runs offline, on CPU, and exits non-zero when thresholds
are breached so it can gate CI.

    >>> from datasets_lint import audit
    >>> report = audit("train.jsonl")
    >>> report.worst.value
    'ok'
"""

__version__ = "1.1.0"

from datasets_lint.api import audit, fix  # noqa: E402
from datasets_lint.config import Config  # noqa: E402
from datasets_lint.dataset import Dataset, load_dataset  # noqa: E402
from datasets_lint.result import CheckResult, Finding, Report, Severity  # noqa: E402

__all__ = [
    "__version__",
    "CheckResult",
    "Config",
    "Dataset",
    "Finding",
    "Report",
    "Severity",
    "audit",
    "fix",
    "load_dataset",
]

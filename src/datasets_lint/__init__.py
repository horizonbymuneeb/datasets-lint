"""datasets-lint — ruff for training data.

Audit a dataset for duplicates, PII, distribution problems and eval-set
contamination. Runs offline, on CPU, and exits non-zero when thresholds
are breached so it can gate CI.
"""

__version__ = "0.1.0"

from datasets_lint.dataset import Dataset, load_dataset  # noqa: E402
from datasets_lint.result import CheckResult, Finding, Report, Severity  # noqa: E402

__all__ = [
    "__version__",
    "CheckResult",
    "Dataset",
    "Finding",
    "Report",
    "Severity",
    "load_dataset",
]

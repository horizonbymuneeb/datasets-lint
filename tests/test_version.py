"""The package must never lie about its own version.

`__version__` comes from the installed distribution metadata, so the only place a
release number is written is `pyproject.toml`. This test proves the two agree —
the failure mode is a wheel that installs as 1.2.0 and reports 1.1.0.
"""

import re
from pathlib import Path

import datasets_lint
from datasets_lint.result import Report


def pyproject_version() -> str:
    text = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match, "pyproject.toml has no [project] version"
    return match.group(1)


def test_version_matches_pyproject():
    assert datasets_lint.__version__ == pyproject_version()


def test_report_defaults_to_the_package_version():
    assert (
        Report(
            dataset_paths=[],
            total_rows=0,
            audited_rows=0,
            sample_size=0,
            seed=0,
            text_column=None,
            label_column=None,
            columns=[],
        ).version
        == datasets_lint.__version__
    )

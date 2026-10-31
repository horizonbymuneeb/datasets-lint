"""One source of truth for the version: the installed distribution's metadata.

`pyproject.toml` is the only place a release number is written; everything else
imports it from here, so a bump cannot leave the package lying about its own name.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    VERSION = version("datasets-lint")
except PackageNotFoundError:  # running from a source tree that was never installed
    VERSION = "0.0.0"

__all__ = ["VERSION"]

"""Loads the vendored axe-core bundle, injected into scanned pages verbatim.

axe.min.js is copied into app/vendor/ at Docker build time from a pinned npm
install (see docker/Dockerfile) -- this module just reads it off disk once.
"""
from __future__ import annotations

from pathlib import Path

AXE_VERSION = "4.10.2"  # keep in sync with the Dockerfile's `npm install axe-core@...`

_VENDOR_PATH = Path(__file__).parent / "vendor" / "axe.min.js"
_cached_source: str | None = None


class AxeSourceMissingError(Exception):
    """Raised when the vendored axe-core bundle isn't present (build misconfigured)."""


def load_axe_source() -> str:
    global _cached_source
    if _cached_source is None:
        if not _VENDOR_PATH.exists():
            raise AxeSourceMissingError(
                f"axe-core bundle not found at {_VENDOR_PATH}. "
                "The Docker build stage that vendors it may not have run."
            )
        _cached_source = _VENDOR_PATH.read_text(encoding="utf-8")
    return _cached_source

"""Optional local web dashboard for the PyScrappy scrapers.

Requires the ``web`` extra: ``pip install 'pyscrappy[web]'``.
"""

from __future__ import annotations

from typing import Any

__all__ = ["create_app", "main"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from pyscrappy.web import app as web_app

        return getattr(web_app, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

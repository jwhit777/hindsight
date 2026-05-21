"""hindsight.web — opt-in FastAPI web UI.

Installed only with the `[web]` extra: `pip install 'hindsight-trace[web]'`.
The core library and CLI do not import this package eagerly; `hindsight
serve` resolves `create_app` lazily, and importing the bare module
without `fastapi` installed is a no-op (so `unittest discover` doesn't
trip when scanning `src/hindsight/`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = ["create_app"]

if TYPE_CHECKING:
    from .app import create_app


def __getattr__(name: str) -> Any:
    """Defer the .app import until `hindsight.web.create_app` is actually
    accessed. Keeps `import hindsight.web` working on installs without
    the `[web]` extra — only attribute access triggers the fastapi import.
    """
    if name == "create_app":
        from .app import create_app

        return create_app
    raise AttributeError(f"module 'hindsight.web' has no attribute {name!r}")

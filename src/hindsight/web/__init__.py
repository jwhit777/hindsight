"""hindsight.web — opt-in FastAPI web UI.

Installed only with the `[web]` extra: `pip install 'hindsight-trace[web]'`.
The core library and CLI do not import this package; `hindsight serve`
imports `hindsight.web.app:create_app` lazily.
"""

from __future__ import annotations

from .app import create_app

__all__ = ["create_app"]

"""FastAPI stub application for Axiom (Issue #2, A1, G0).

Re-exports `engine.api.app` so that running either:
    uvicorn api.main:app
or:
    uvicorn engine.api:app
works identically.
"""

from engine.api import app

__all__ = ["app"]

"""JobHound server package."""

from typing import Any


def create_app(*args: Any, **kwargs: Any):
    """Import lazily so persistence helpers have no application side effects."""
    from .app import create_app as factory
    return factory(*args, **kwargs)


__all__ = ["create_app"]

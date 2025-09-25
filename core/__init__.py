# core/__init__.py
"""
Lightweight package initializer to avoid circular imports.

Only export UI helpers that the top-level app needs.
Submodules (io, optimizer, matrix, etc.) are imported directly
by consumers, e.g. `import core.io as io`.
"""

from .help import render_help_button

__all__ = ["render_help_button"]

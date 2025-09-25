# core/__init__.py
"""
Core package exports.

We expose render_help_button() so the app can show the
“How this app works” panel anywhere (main page or sidebar).
"""

from . import io, economics, optimizer, constants, battery, matrix, portfolio, tolling
from .help import render_help_button  # <-- used by app.py

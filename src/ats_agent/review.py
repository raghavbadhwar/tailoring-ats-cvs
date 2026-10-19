"""Single review surface; legacy modules delegate here during migration."""
from __future__ import annotations

from .reports import render_html, render_markdown

__all__ = ["render_html", "render_markdown"]

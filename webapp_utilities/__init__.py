"""Shared Flask-assembly seam for world_map and world_explorer.

App-agnostic web-layer helpers (Flask factory, theme CSS rendering) that both
apps depend on. Kept separate from `world_reader` so the data-layer package
stays free of Flask/CORS dependencies.
"""

from webapp_utilities.factory import make_app, make_context_accessor
from webapp_utilities.theme_css import (
    hex_to_rgb, build_css_vars, build_root_block, render_theme_css, resolve_theme,
)

__all__ = [
    'make_app', 'make_context_accessor',
    'hex_to_rgb', 'build_css_vars', 'build_root_block', 'render_theme_css', 'resolve_theme',
]

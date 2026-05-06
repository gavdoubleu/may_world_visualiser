"""Config, theme, and index-page blueprint."""

from flask import Blueprint, jsonify, render_template
import logging

from world_map.themes.theme_css import build_root_block
from world_map.context import get_app_context

logger = logging.getLogger(__name__)

config_bp = Blueprint('config', __name__)


@config_bp.route('/')
def index():
    """Serve the main interactive map page."""
    ctx = get_app_context()
    logo_path = (ctx.theme_config or {}).get('logo_path', '')
    logo_url = f'/static/{logo_path}' if logo_path else ''
    return render_template('index.html', logo_url=logo_url)


@config_bp.route('/api/map/config')
def get_map_config():
    """Get map configuration including background type and bounds."""
    try:
        ctx = get_app_context()
        config = dict(ctx.map_config)
        config['slim_mode'] = hasattr(ctx.world, '_unit_statistics')
        return jsonify(config)
    except Exception as e:
        logger.error(f"Error getting map config: {e}")
        return jsonify({'error': str(e)}), 500


@config_bp.route('/api/panel/config')
def get_panel_config():
    """Get info panel configuration for customizing displayed attributes."""
    return jsonify(get_app_context().panel_config)


@config_bp.route('/api/theme')
def get_theme():
    """Return theme configuration as JSON."""
    return jsonify(get_app_context().theme_config)


@config_bp.route('/api/theme.css')
def get_theme_css():
    """Return a CSS stylesheet generated from the active theme config."""
    from flask import current_app
    theme = get_app_context().theme_config or {}
    fonts = theme.get('fonts', {})

    display_font = fonts.get('display', 'sans-serif')
    body_font = fonts.get('body', 'sans-serif')
    display_file = fonts.get('display_file', '')
    body_file = fonts.get('body_file', '')

    css_lines = []

    if display_file:
        css_lines.append(
            f"@font-face {{\n"
            f"    font-family: '{display_font}';\n"
            f"    src: url('/static/fonts/{display_file}') format('woff2');\n"
            f"    font-weight: normal;\n"
            f"    font-style: normal;\n"
            f"}}"
        )
    if body_file and body_file != display_file:
        css_lines.append(
            f"@font-face {{\n"
            f"    font-family: '{body_font}';\n"
            f"    src: url('/static/fonts/{body_file}') format('woff2');\n"
            f"    font-weight: normal;\n"
            f"    font-style: normal;\n"
            f"}}"
        )

    css_lines.append(build_root_block(theme))

    return current_app.response_class(
        response="\n\n".join(css_lines),
        status=200,
        mimetype='text/css'
    )

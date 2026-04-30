"""Config, theme, and index-page blueprint."""

from flask import Blueprint, jsonify, render_template, current_app
import logging

from world_map.themes.theme_css import build_root_block

logger = logging.getLogger(__name__)

config_bp = Blueprint('config', __name__)


@config_bp.route('/')
def index():
    """Serve the main interactive map page."""
    from world_map.app import load_theme_config
    theme_config = current_app.config.get('THEME_CONFIG')
    if theme_config is None:
        theme_config = load_theme_config()
        current_app.config['THEME_CONFIG'] = theme_config
    logo_path = (theme_config or {}).get('logo_path', '')
    logo_url = f'/static/{logo_path}' if logo_path else ''
    return render_template('index.html', logo_url=logo_url)


@config_bp.route('/api/map/config')
def get_map_config():
    """Get map configuration including background type and bounds."""
    try:
        world = current_app.config['WORLD']
        config = dict(current_app.config['MAP_CONFIG'])
        config['slim_mode'] = hasattr(world, '_unit_statistics')
        return jsonify(config)
    except Exception as e:
        logger.error(f"Error getting map config: {e}")
        return jsonify({'error': str(e)}), 500


@config_bp.route('/api/panel/config')
def get_panel_config():
    """Get info panel configuration for customizing displayed attributes."""
    from world_map.app import load_panel_config
    panel_config = current_app.config.get('PANEL_CONFIG')
    if panel_config is None:
        panel_config = load_panel_config()
        current_app.config['PANEL_CONFIG'] = panel_config
    return jsonify(panel_config)


@config_bp.route('/api/theme')
def get_theme():
    """Return theme configuration as JSON."""
    from world_map.app import load_theme_config
    theme_config = current_app.config.get('THEME_CONFIG')
    if theme_config is None:
        theme_config = load_theme_config()
        current_app.config['THEME_CONFIG'] = theme_config
    return jsonify(theme_config)


@config_bp.route('/api/theme.css')
def get_theme_css():
    """Return a CSS stylesheet generated from the active theme config."""
    from world_map.app import load_theme_config
    theme_config = current_app.config.get('THEME_CONFIG')
    if theme_config is None:
        theme_config = load_theme_config()
        current_app.config['THEME_CONFIG'] = theme_config

    theme = theme_config or {}
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

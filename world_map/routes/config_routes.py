"""Config, theme, and index-page blueprint."""

from flask import Blueprint, jsonify, render_template
import logging

from webapp_utilities.theme_css import render_theme_css
from world_map.context import get_app_context

logger = logging.getLogger(__name__)

config_bp = Blueprint('config', __name__)


@config_bp.route('/')
def index():
    """Serve the main interactive map page."""
    try:
        ctx = get_app_context()
        logo_path = (ctx.app_config.theme or {}).get('logo_path', '')
        logo_url = f'/static/{logo_path}' if logo_path else ''
        return render_template('index.html', logo_url=logo_url)
    except Exception as e:
        logger.error(f"Error rendering index: {e}")
        return jsonify({'error': str(e)}), 500


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
    try:
        return jsonify(get_app_context().app_config.panel)
    except Exception as e:
        logger.error(f"Error getting panel config: {e}")
        return jsonify({'error': str(e)}), 500


@config_bp.route('/api/theme')
def get_theme():
    """Return theme configuration as JSON."""
    try:
        return jsonify(get_app_context().app_config.theme)
    except Exception as e:
        logger.error(f"Error getting theme: {e}")
        return jsonify({'error': str(e)}), 500


@config_bp.route('/api/theme.css')
def get_theme_css():
    """Return a CSS stylesheet generated from the active theme config."""
    try:
        from flask import current_app
        theme = get_app_context().app_config.theme or {}
        return current_app.response_class(
            response=render_theme_css(theme),
            status=200,
            mimetype='text/css'
        )
    except Exception as e:
        logger.error(f"Error generating theme CSS: {e}")
        return jsonify({'error': str(e)}), 500

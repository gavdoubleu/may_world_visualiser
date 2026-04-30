#!/usr/bin/env python3
"""
World Map - Interactive visualization for World instances.

This Flask application provides an interactive map interface for exploring
World instances containing geography, population, venues, and households.
"""

from flask import Flask, jsonify
from flask_cors import CORS
import logging
import yaml
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_panel_config(config_path=None):
    """Load info panel configuration from YAML file."""
    if config_path is None:
        config_path = Path(__file__).parent / 'yaml' / 'info_panel_config.yaml'

    try:
        with open(config_path, 'r') as f:
            panel_config = yaml.safe_load(f)
        logger.info(f"Loaded panel config from {config_path}")
    except FileNotFoundError:
        logger.warning(f"Panel config not found at {config_path}, using defaults")
        panel_config = _get_default_panel_config()
    except Exception as e:
        logger.error(f"Error loading panel config: {e}")
        panel_config = _get_default_panel_config()

    return panel_config


def load_theme_config(app_config_path=None):
    """Load theme from app_config.yaml, then from yaml/themes/{theme}.yaml."""
    if app_config_path is None:
        app_config_path = Path(__file__).parent / 'yaml' / 'app_config.yaml'

    theme_name = 'dark_scientific'
    try:
        with open(app_config_path, 'r') as f:
            app_config = yaml.safe_load(f)
        theme_name = app_config.get('theme', 'dark_scientific')
    except FileNotFoundError:
        logger.warning(f"app_config.yaml not found at {app_config_path}, defaulting to dark_scientific")

    theme_path = Path(__file__).parent / 'yaml' / 'themes' / f'{theme_name}.yaml'
    try:
        with open(theme_path, 'r') as f:
            theme_config = yaml.safe_load(f)
        logger.info(f"Loaded theme '{theme_name}' from {theme_path}")
    except FileNotFoundError:
        logger.warning(f"Theme file not found: {theme_path}, using empty theme")
        theme_config = {}

    return theme_config


def _convert_numpy_types(obj):
    """Recursively convert numpy types to Python native types for JSON serialization."""
    import numpy as np

    if obj is None:
        return None
    if isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    if isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.str_):
        return str(obj)
    if isinstance(obj, dict):
        return {str(k): _convert_numpy_types(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_convert_numpy_types(item) for item in obj]
    return obj


def _get_default_panel_config():
    """Return default panel configuration.

    Uses same nested structure as info_panel_config.yaml for consistency with event_visualisation.yaml.
    """
    return {
        'geo_unit_panel': {
            'title_field': 'name',
            'popup': {'enabled': True},
            'detail_sections': []
        },
        'venue_panel': {
            'title_field': 'name',
            'popup': {'enabled': True},
            'detail_sections': []
        },
        'marker_styles': {
            'geo_unit': {
                'size': {'method': 'sqrt', 'min_radius': 5, 'max_radius': 15, 'scale': 0.5},
                'border': {'color': '#808080', 'width': 1, 'opacity': 1},
                'fill_opacity': 0.7,
                'zoom_scaling': {'enabled': True, 'base_zoom': 6, 'scale_exponent': 0.5, 'min_scale': 0.3, 'max_scale': 3.0}
            },
            'venue': {
                'size': {'radius': 6},
                'border': {'color': '#ffffff', 'width': 1, 'opacity': 1},
                'fill_opacity': 0.8,
                'zoom_scaling': {'enabled': True, 'base_zoom': 6, 'scale_exponent': 0.5, 'min_scale': 0.3, 'max_scale': 3.0}
            }
        }
    }


def load_event_config(config_path=None):
    """Load event visualization configuration from YAML file."""
    if config_path is None:
        config_path = Path(__file__).parent / 'yaml' / 'event_visualisation.yaml'

    try:
        with open(config_path, 'r') as f:
            event_config = yaml.safe_load(f)
        logger.info(f"Loaded event config from {config_path}")
    except FileNotFoundError:
        logger.warning(f"Event config not found at {config_path}, using defaults")
        event_config = _get_default_event_config()
    except Exception as e:
        logger.error(f"Error loading event config: {e}")
        event_config = _get_default_event_config()

    return event_config


def _get_default_event_config():
    """Return default event configuration.

    Uses same nested structure as YAML config files for consistency with info_panel_config.yaml.
    """
    return {
        'event_types': {
            'infections': {
                'label': 'Infections',
                'default_visible': True,
                'marker': {
                    'color': '#e74c3c',
                    'border': {'color': '#ffffff', 'width': 2, 'opacity': 0.8},
                    'fill_opacity': 0.8,
                    'size_scale': 1.0
                },
                'color_thresholds': [
                    {'max_count': 5, 'color': '#fee5d9', 'label': 'Very Low'},
                    {'max_count': 20, 'color': '#fcae91', 'label': 'Low'},
                    {'max_count': 50, 'color': '#fb6a4a', 'label': 'Medium'},
                    {'max_count': 100, 'color': '#de2d26', 'label': 'High'},
                    {'max_count': None, 'color': '#a50f15', 'label': 'Very High'}
                ],
                'use_relative_scaling': False,
                'gradient': {'low': '#fee5d9', 'medium': '#fcae91', 'high': '#fb6a4a', 'very_high': '#cb181d'}
            },
            'deaths': {
                'label': 'Deaths',
                'default_visible': True,
                'marker': {
                    'color': '#2c3e50',
                    'border': {'color': '#ffffff', 'width': 2, 'opacity': 0.9},
                    'fill_opacity': 0.9,
                    'size_scale': 1.2
                },
                'color_thresholds': [
                    {'max_count': 1, 'color': '#d9d9d9', 'label': 'Very Low'},
                    {'max_count': 5, 'color': '#969696', 'label': 'Low'},
                    {'max_count': 15, 'color': '#525252', 'label': 'Medium'},
                    {'max_count': 30, 'color': '#252525', 'label': 'High'},
                    {'max_count': None, 'color': '#000000', 'label': 'Very High'}
                ],
                'use_relative_scaling': False,
                'gradient': {'low': '#d9d9d9', 'medium': '#969696', 'high': '#525252', 'very_high': '#252525'}
            }
        },
        'time': {
            'aggregation_window': 1.0,
            'playback_interval_ms': 500,
            'rolling_window_days': 1
        },
        'display': {
            'default_mode': 'choropleth',
            'choropleth': {
                'size': {'method': 'sqrt', 'min_radius': 6, 'max_radius': 35, 'scale': 2.0},
                'border': {'color': '#333333', 'width': 1, 'opacity': 0.8},
                'fill_opacity': 0.7
            },
            'markers': {
                'size': {'method': 'sqrt', 'min_radius': 5, 'max_radius': 40, 'scale': 1.5},
                'border': {'color': '#ffffff', 'width': 2, 'opacity': 1},
                'fill_opacity': 0.6
            },
            'zoom_scaling': {'enabled': True, 'base_zoom': 6, 'scale_exponent': 0.5, 'min_scale': 0.3, 'max_scale': 3.0}
        },
        'aggregation': {'method': 'count', 'cumulative': False},
        'legend': {'position': 'bottomright', 'show_threshold_labels': True, 'show_totals': True, 'title': 'Event Counts'},
        'popup': {'show_count': True, 'show_rate': True, 'show_geo_unit_name': True}
    }


def initialize_events(events_path, flask_app, world=None):
    """Initialize event loader with optional world instance for geo coordinates."""
    try:
        from world_map.events.event_loader import load_events_with_world
        event_loader = load_events_with_world(events_path, world)
        flask_app.config['EVENT_LOADER'] = event_loader
        logger.info(f"Event loader initialized from {events_path}")
    except Exception as e:
        logger.error(f"Failed to initialize event loader: {e}")
        flask_app.config['EVENT_LOADER'] = None


def get_world():
    """Get the current World instance."""
    from flask import current_app
    world = current_app.config.get('WORLD')
    if world is None:
        raise RuntimeError("World instance not initialized. Call create_app() first.")
    return world


def get_event_loader():
    """Get the event loader instance."""
    from flask import current_app
    return current_app.config.get('EVENT_LOADER')


def create_app(world, map_config=None, panel_config_path=None):
    """
    Initialize the Flask app with a World instance and optional map configuration.

    Args:
        world: World instance to visualize
        map_config: Dict with optional keys:
            - background_type: 'osm' (default) or 'image'
            - image_url: URL or path to background image (required if background_type='image')
            - bounds: [[south, west], [north, east]] geographic bounds (required if background_type='image')
            - attribution: Attribution text for the image
        panel_config_path: Path to info panel YAML config (optional)

    Returns:
        Flask app instance
    """
    app = Flask(__name__)
    CORS(app)

    app.config['WORLD'] = world

    default_map_config = {
        'background_type': 'osm',
        'image_url': None,
        'bounds': None,
        'attribution': None
    }
    if map_config:
        default_map_config.update(map_config)
    app.config['MAP_CONFIG'] = default_map_config

    # Build a flat venue index keyed by venue.id (Python memory address)
    venue_index = {}
    if world.venues:
        for venue in world.venues.get_all_venues().values():
            venue_index[venue.id] = venue
    app.config['VENUE_INDEX'] = venue_index

    # Load panel, theme, and event configuration
    app.config['PANEL_CONFIG'] = load_panel_config(panel_config_path)
    app.config['THEME_CONFIG'] = load_theme_config()
    app.config['EVENT_CONFIG'] = load_event_config()

    logger.info(f"Initialized world map with: {world}")
    log_cfg = {k: (v[:60] + '…' if isinstance(v, str) and len(v) > 60 else v)
               for k, v in default_map_config.items()}
    logger.info(f"Map configuration: {log_cfg}")

    # Register blueprints
    from world_map.routes.geography import geography_bp
    from world_map.routes.population import population_bp
    from world_map.routes.venues import venues_bp
    from world_map.routes.events import events_bp
    from world_map.routes.config_routes import config_bp
    app.register_blueprint(geography_bp)
    app.register_blueprint(population_bp)
    app.register_blueprint(venues_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(config_bp)

    # ============================================================================
    # Error Handlers
    # ============================================================================

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not found'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error'}), 500

    return app


# Keep initialize_app as an alias for backwards compatibility
def initialize_app(world, map_config=None, panel_config_path=None):
    """Alias for create_app() — kept for backwards compatibility."""
    return create_app(world, map_config=map_config, panel_config_path=panel_config_path)


if __name__ == '__main__':
    logger.warning("Run this app using the launcher script, not directly!")
    logger.warning("Example: python launch_world_map.py")

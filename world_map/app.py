#!/usr/bin/env python3
"""
World Map - Interactive visualization for World instances.

This Flask application provides an interactive map interface for exploring
World instances containing geography, population, venues, and households.
"""

from flask import Flask, jsonify
from flask_cors import CORS
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def initialize_events(events_path, flask_app, world=None):
    """Initialize event aggregator with optional world instance for geo coordinates."""
    try:
        from world_map.events.event_loader import load_events_with_world
        from world_map.context import _CTX_KEY
        event_aggregator = load_events_with_world(events_path, world)
        flask_app.config['EVENT_LOADER'] = event_aggregator
        ctx = flask_app.config.get(_CTX_KEY)
        if ctx is not None:
            ctx.event_loader = event_aggregator
        logger.info(f"Event aggregator initialized from {events_path}")
    except Exception as e:
        logger.error(f"Failed to initialize event aggregator: {e}")
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


def create_app(world, map_config=None, config_path=None):
    """Initialize the Flask app with a World instance and optional map configuration.

    map_config keys: background_type, image_url, bounds, attribution.
    config_path: path to config.yaml; defaults to world_map/yaml/config.yaml.
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

    # Build a flat venue index keyed by venue.id
    venue_index = {}
    if world.venues:
        for venue in world.venues.get_all_venues().values():
            venue_index[venue.id] = venue
    app.config['VENUE_INDEX'] = venue_index

    from world_map.config import AppConfig, _DEFAULT_CONFIG_PATH
    if config_path is None:
        config_path = _DEFAULT_CONFIG_PATH
    cfg = AppConfig.load(Path(config_path))

    # Build map projection from config
    from world_map.projection import build as _build_projection, MapProjectionConfig
    try:
        _projection: MapProjectionConfig = _build_projection(cfg.projection_type, **cfg.projection_kwargs)
    except (KeyError, ImportError) as _exc:
        logger.warning(f"Projection init failed ({_exc}); using web_mercator")
        from world_map.projection.web_mercator import WebMercatorConfig
        _projection = WebMercatorConfig()

    if world.geography:
        _all_coords = [
            unit.coordinates
            for level in world.geography.levels
            for unit in world.geography.get_units_by_level(level).values()
            if unit.coordinates
        ]
        if _all_coords:
            _lats, _lons = zip(*_all_coords)
            _projection.seed_from_coordinates(list(_lats), list(_lons))

    default_map_config['crs'] = _projection.leaflet_crs_spec()
    logger.info(f"Map projection: {_projection.name} (EPSG:{_projection.native_epsg})")
    logger.info(f"Initialized world map with: {world}")

    # Build typed AppContext — single source of truth for all route dependencies
    from world_map.context import AppContext, _CTX_KEY
    app.config[_CTX_KEY] = AppContext(
        world=world,
        venue_index=venue_index,
        projection=_projection,
        map_config=default_map_config,
        app_config=cfg,
        event_loader=app.config.get('EVENT_LOADER'),
    )

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


if __name__ == '__main__':
    logger.warning("Run this app using the launcher script, not directly!")
    logger.warning("Example: python launch_world_map.py")

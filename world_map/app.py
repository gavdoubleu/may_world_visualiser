#!/usr/bin/env python3
"""
World Map - Interactive visualization for World instances.

This Flask application provides an interactive map interface for exploring
World instances containing geography, population, venues, and households.
"""

import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def initialize_events(events_path, flask_app, world=None):
    """Initialize event aggregator with optional world instance for geo coordinates.

    Reaches into flask_app.config directly (not get_app_context/current_app):
    called outside a request/app context, while current_app is unavailable.
    """
    from world_map.context import _CTX_KEY
    try:
        from world_map.events.event_loader import load_events_with_world
        event_aggregator = load_events_with_world(events_path, world)
        flask_app.config[_CTX_KEY].event_loader = event_aggregator
        logger.info(f"Event aggregator initialized from {events_path}")
    except Exception as e:
        logger.error(f"Failed to initialize event aggregator: {e}")


def create_app(world, hdf5_path, map_config=None, config_path=None):
    """Initialize the Flask app with a WorldStore and optional map configuration.

    map_config keys: background_type, image_url, bounds, attribution.
    config_path: path to config.yaml; defaults to world_map/yaml/config.yaml.
    hdf5_path: path to the world_state.h5 backing `world` — wired into
        RecordReader for on-demand single-record reads (people, venues,
        persons), mirroring world_explorer's wiring.
    """
    default_map_config = {
        'background_type': 'osm',
        'image_url': None,
        'bounds': None,
        'attribution': None
    }
    if map_config:
        default_map_config.update(map_config)

    from world_reader import RecordReader
    record_reader = RecordReader(hdf5_path, world)

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
        _all_coords = world.geography.geo_unit_coords().values()
        if _all_coords:
            _lats, _lons = zip(*_all_coords)
            _projection.seed_from_coordinates(list(_lats), list(_lons))

    default_map_config['crs'] = _projection.leaflet_crs_spec()
    logger.info(f"Map projection: {_projection.name} (EPSG:{_projection.native_epsg})")
    logger.info(f"Initialized world map with: {world}")

    # Build typed AppContext — single source of truth for all route dependencies
    from world_map.context import AppContext, _CTX_KEY
    context = AppContext(
        world=world,
        record_reader=record_reader,
        projection=_projection,
        map_config=default_map_config,
        app_config=cfg,
        event_loader=None,
    )

    from webapp_utilities import make_app
    from world_map.routes.geography import geography_bp
    from world_map.routes.population import population_bp
    from world_map.routes.venues import venues_bp
    from world_map.routes.venue_browse import venue_browse_bp
    from world_map.routes.events import events_bp
    from world_map.routes.config_routes import config_bp

    return make_app(
        __name__,
        blueprints=[geography_bp, population_bp, venues_bp, venue_browse_bp, events_bp, config_bp],
        context=context,
        context_key=_CTX_KEY,
    )


if __name__ == '__main__':
    logger.warning("Run this app using the launcher script, not directly!")
    logger.warning("Example: python launch_world_map.py")

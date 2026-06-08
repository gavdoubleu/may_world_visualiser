"""Geography API blueprint."""

from flask import Blueprint, jsonify, request
import logging

from world_map.utils import convert_numpy_types
from world_map.context import get_app_context

logger = logging.getLogger(__name__)

geography_bp = Blueprint('geography', __name__)


@geography_bp.route('/api/geography/levels')
def get_geography_levels():
    """Get available geography levels."""
    try:
        world = get_app_context().world
        if not world.geography:
            return jsonify({'levels': []})

        return jsonify({
            'levels': world.geography.levels,
            'units_per_level': {
                level: len(world.geography.get_units_by_level(level))
                for level in world.geography.levels
            }
        })
    except Exception as e:
        logger.error(f"Error getting geography levels: {e}")
        return jsonify({'error': str(e)}), 500


@geography_bp.route('/api/geography/<level>')
def get_geography_level(level):
    """Get all geographical units at a specific level as GeoJSON."""
    try:
        world = get_app_context().world
        if not world.geography:
            return jsonify({'type': 'FeatureCollection', 'features': []})

        units = world.geography.get_units_by_level(level)
        if not units:
            return jsonify({'type': 'FeatureCollection', 'features': []})

        features = []
        for unit_name, unit in units.items():
            if not unit.coordinates:
                continue

            lat, lon = unit.coordinates
            stats = world._unit_statistics.get(unit_name)

            feature = {
                'type': 'Feature',
                'properties': {
                    'id': int(unit.id) if hasattr(unit.id, 'item') else unit.id,
                    'name': str(unit.name),
                    'level': str(unit.level),
                    'population': stats.population if stats else 0,
                    'venues_count': stats.venues_count if stats else 0,
                    'venue_types': stats.venue_types if stats else {},
                    'has_parent': unit.parent is not None,
                    'children_count': int(len(unit.children)) if unit.children else 0
                },
                'geometry': {
                    'type': 'Point',
                    'coordinates': [float(lon), float(lat)]
                }
            }
            features.append(feature)

        geojson = {'type': 'FeatureCollection', 'features': features}
        logger.info(f"Returned {len(features)} features for level {level}")
        return jsonify(geojson)

    except Exception as e:
        logger.error(f"Error getting geography level {level}: {e}")
        return jsonify({'error': str(e)}), 500


@geography_bp.route('/api/geography/unit/<unit_name>')
def get_unit_details(unit_name):
    """Get detailed information about a specific geographical unit."""
    try:
        ctx = get_app_context()
        world = ctx.world
        if not world.geography:
            return jsonify({'error': 'No geography data'}), 404

        unit = world.geography.get_unit(unit_name)
        if not unit:
            return jsonify({'error': f'Unit {unit_name} not found'}), 404

        stats = world._unit_statistics.get(unit_name)
        if stats is None:
            return jsonify({'error': f'No statistics for unit {unit_name}'}), 404

        parent_info = None
        if unit.parent:
            parent_info = {
                'id': unit.parent.id,
                'name': unit.parent.name,
                'level': unit.parent.level
            }

        children_info = []
        for child in (unit.children or []):
            child_stats = world._unit_statistics.get(child.name)
            children_info.append({
                'id': child.id,
                'name': child.name,
                'level': child.level,
                'population': child_stats.population if child_stats else 0,
            })

        return jsonify(convert_numpy_types({
            'id': unit.id,
            'name': unit.name,
            'level': unit.level,
            'coordinates': unit.coordinates,
            **stats.to_dict(),
            'parent': parent_info,
            'children': children_info,
            'properties': unit.properties,
            'slim_mode': True,
            'display_name_enabled': ctx.geo_unit_names_enabled,
            'display_name': (ctx.geo_unit_names or {}).get(unit.name) if ctx.geo_unit_names_enabled else None,
        }))

    except Exception as e:
        logger.error(f"Error getting unit details for {unit_name}: {e}")
        return jsonify({'error': str(e)}), 500


@geography_bp.route('/api/geography/unit/<unit_name>/people')
def get_unit_people(unit_name):
    """Get list of people in a geographical unit's subtree, paginated.

    NOTE: returns the unit's whole subtree (matching WorldExplorer's
    `load_unit_people`) — the eager route's `include_descendants=false`
    default (direct residents only) is dropped, since the frontend never
    set that param. `activities`/`primary_activity` are empty/null per the
    deferred-stats decision (see docs/handoff/activity-stats-on-demand.md).
    """
    try:
        ctx = get_app_context()
        world = ctx.world
        if not world.geography:
            return jsonify({'error': 'No geography data'}), 404

        if not world.geography.get_unit(unit_name):
            return jsonify({'error': f'Unit {unit_name} not found'}), 404

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        per_page = min(per_page, 200)

        return jsonify(ctx.explorer_loader.load_unit_people(unit_name, page, per_page))

    except Exception as e:
        logger.error(f"Error getting people for unit {unit_name}: {e}")
        return jsonify({'error': str(e)}), 500

"""Geography API blueprint."""

from flask import Blueprint, jsonify, request
import logging

from world_map.utils import convert_numpy_types
from world_map.context import get_app_context
from world_map.core.pagination import paginate

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
    """Get list of people in a geographical unit with pagination."""
    try:
        world = get_app_context().world
        if not world.geography:
            return jsonify({'error': 'No geography data'}), 404

        unit = world.geography.get_unit(unit_name)
        if not unit:
            return jsonify({'error': f'Unit {unit_name} not found'}), 404

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        per_page = min(per_page, 200)

        include_descendants = request.args.get('include_descendants', 'false').lower() == 'true'
        all_people = unit.get_people() if include_descendants else (list(unit.people) if unit.people else [])
        total_count = len(all_people)

        sl = paginate(all_people, page, per_page)

        people_data = []
        for person in sl.items:
            primary_activity = None
            if hasattr(person, 'activity_map') and person.activity_map:
                if 'primary_activity' in person.activity_map:
                    for venue_type, subsets in person.activity_map['primary_activity'].items():
                        if subsets:
                            subset = subsets[0] if isinstance(subsets, list) else subsets
                            if subset and hasattr(subset, 'venue'):
                                primary_activity = {
                                    'type': venue_type,
                                    'venue_name': getattr(subset.venue, 'name', 'unknown')
                                }
                                break

            people_data.append({
                'id': person.id,
                'age': person.age,
                'sex': person.sex,
                'activities': list(person.activities) if isinstance(person.activities, set) else person.activities,
                'primary_activity': primary_activity
            })

        return jsonify({
            'unit_name':   unit_name,
            'total_count': sl.total,
            'page':        sl.page,
            'per_page':    sl.per_page,
            'total_pages': sl.total_pages,
            'people':      people_data,
        })

    except Exception as e:
        logger.error(f"Error getting people for unit {unit_name}: {e}")
        return jsonify({'error': str(e)}), 500

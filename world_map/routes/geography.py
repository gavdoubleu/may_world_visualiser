"""Geography API blueprint."""

from flask import Blueprint, jsonify, request, current_app
from collections import defaultdict
import logging

from world_map.app import _convert_numpy_types

logger = logging.getLogger(__name__)

geography_bp = Blueprint('geography', __name__)


@geography_bp.route('/api/geography/levels')
def get_geography_levels():
    """Get available geography levels."""
    try:
        world = current_app.config['WORLD']
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
    """
    Get all geographical units at a specific level as GeoJSON.

    Returns point features with coordinates and metadata.
    For units with children, aggregates population and venue counts from all descendants.
    """
    try:
        world = current_app.config['WORLD']
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

            # Use get_people() to recursively get all people from unit and descendants
            all_people = unit.get_people()
            population = len(all_people) if all_people else 0

            # Aggregate venues from unit and all descendants
            all_venues = list(unit.venues) if unit.venues else []
            if unit.children:
                for descendant in unit.get_descendants():
                    if descendant.venues:
                        all_venues.extend(descendant.venues)
            venues_count = len(all_venues)

            # Get venue breakdown from all aggregated venues
            venue_types = defaultdict(int)
            for venue in all_venues:
                venue_types[str(venue.type)] += 1

            feature = {
                'type': 'Feature',
                'properties': {
                    'id': int(unit.id) if hasattr(unit.id, 'item') else unit.id,
                    'name': str(unit.name),
                    'level': str(unit.level),
                    'population': int(population),
                    'venues_count': int(venues_count),
                    'venue_types': dict(venue_types),
                    'has_parent': unit.parent is not None,
                    'children_count': int(len(unit.children)) if unit.children else 0
                },
                'geometry': {
                    'type': 'Point',
                    'coordinates': [float(lon), float(lat)]
                }
            }
            features.append(feature)

        geojson = {
            'type': 'FeatureCollection',
            'features': features
        }

        logger.info(f"Returned {len(features)} features for level {level}")
        return jsonify(geojson)

    except Exception as e:
        logger.error(f"Error getting geography level {level}: {e}")
        return jsonify({'error': str(e)}), 500


@geography_bp.route('/api/geography/unit/<unit_name>')
def get_unit_details(unit_name):
    """Get detailed information about a specific geographical unit.

    In slim mode, returns pre-computed statistics (no venue list, no people list).
    In full mode, aggregates statistics from all descendants.
    """
    try:
        world = current_app.config['WORLD']
        if not world.geography:
            return jsonify({'error': 'No geography data'}), 404

        unit = world.geography.get_unit(unit_name)
        if not unit:
            return jsonify({'error': f'Unit {unit_name} not found'}), 404

        # Parent and children info (needed in both modes)
        parent_info = None
        if unit.parent:
            parent_info = {
                'id': unit.parent.id,
                'name': unit.parent.name,
                'level': unit.parent.level
            }

        # ---- Slim mode: serve pre-computed stats ----------------------------
        unit_statistics = getattr(world, '_unit_statistics', None)
        if unit_statistics is not None:
            pre = unit_statistics.get(unit_name, {})
            children_info = []
            if unit.children:
                for child in unit.children:
                    child_pre = unit_statistics.get(child.name, {})
                    children_info.append({
                        'id': child.id,
                        'name': child.name,
                        'level': child.level,
                        'population': child_pre.get('population', 0),
                    })
            venues_count = sum(pre.get('venue_types', {}).values())
            geo_unit_names = current_app.config.get('GEO_UNIT_NAMES')
            names_enabled = current_app.config.get('GEO_UNIT_NAMES_ENABLED', False)
            return jsonify(_convert_numpy_types({
                'id': unit.id,
                'name': unit.name,
                'level': unit.level,
                'coordinates': unit.coordinates,
                'population': pre.get('population', 0),
                'age_distribution': pre.get('age_distribution', {}),
                'sex_distribution': pre.get('sex_distribution', {}),
                'venues_count': venues_count,
                'venue_types': pre.get('venue_types', {}),
                'activity_counts': pre.get('activity_counts', {}),
                'parent': parent_info,
                'children': children_info,
                'properties': unit.properties,
                'slim_mode': True,
                'display_name_enabled': names_enabled,
                'display_name': (geo_unit_names or {}).get(unit.name) if names_enabled else None,
            }))

        # ---- Full mode: compute on the fly ----------------------------------
        all_people = unit.get_people()

        age_groups = {
            '0-15': 0, '16-24': 0, '25-34': 0,
            '35-49': 0, '50-64': 0, '65+': 0
        }
        sex_distribution = defaultdict(int)
        for person in all_people:
            if person.age <= 15:    age_groups['0-15'] += 1
            elif person.age <= 24:  age_groups['16-24'] += 1
            elif person.age <= 34:  age_groups['25-34'] += 1
            elif person.age <= 49:  age_groups['35-49'] += 1
            elif person.age <= 64:  age_groups['50-64'] += 1
            else:                   age_groups['65+'] += 1
            sex_distribution[person.sex] += 1

        all_venues = list(unit.venues) if unit.venues else []
        if unit.children:
            for descendant in unit.get_descendants():
                if descendant.venues:
                    all_venues.extend(descendant.venues)

        venue_details = []
        venue_types = defaultdict(int)
        for venue in all_venues:
            venue_types[venue.type] += 1
            if len(venue_details) < 50:
                venue_details.append({
                    'id': venue.id,
                    'name': venue.name,
                    'type': venue.type,
                    'coordinates': venue.coordinates,
                    'properties': venue.properties
                })

        children_info = []
        if unit.children:
            for child in unit.children:
                children_info.append({
                    'id': child.id,
                    'name': child.name,
                    'level': child.level,
                    'population': len(child.get_people()),
                })

        geo_unit_names = current_app.config.get('GEO_UNIT_NAMES')
        names_enabled = current_app.config.get('GEO_UNIT_NAMES_ENABLED', False)
        return jsonify({
            'id': unit.id,
            'name': unit.name,
            'level': unit.level,
            'coordinates': unit.coordinates,
            'population': len(all_people),
            'age_distribution': age_groups,
            'sex_distribution': dict(sex_distribution),
            'venues_count': len(all_venues),
            'venue_types': dict(venue_types),
            'venue_details': venue_details,
            'parent': parent_info,
            'children': children_info,
            'properties': unit.properties,
            'slim_mode': False,
            'display_name_enabled': names_enabled,
            'display_name': (geo_unit_names or {}).get(unit.name) if names_enabled else None,
        })

    except Exception as e:
        logger.error(f"Error getting unit details for {unit_name}: {e}")
        return jsonify({'error': str(e)}), 500


@geography_bp.route('/api/geography/unit/<unit_name>/people')
def get_unit_people(unit_name):
    """Get list of people in a geographical unit with pagination."""
    try:
        world = current_app.config['WORLD']
        if not world.geography:
            return jsonify({'error': 'No geography data'}), 404

        unit = world.geography.get_unit(unit_name)
        if not unit:
            return jsonify({'error': f'Unit {unit_name} not found'}), 404

        # Pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        per_page = min(per_page, 200)  # Cap at 200 per page

        # Get all people from unit (and optionally descendants)
        include_descendants = request.args.get('include_descendants', 'false').lower() == 'true'

        if include_descendants:
            all_people = unit.get_people()
        else:
            all_people = list(unit.people) if unit.people else []

        total_count = len(all_people)

        # Apply pagination
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_people = all_people[start_idx:end_idx]

        # Build person summaries
        people_data = []
        for person in paginated_people:
            # Get primary activity info
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
            'unit_name': unit_name,
            'total_count': total_count,
            'page': page,
            'per_page': per_page,
            'total_pages': (total_count + per_page - 1) // per_page,
            'people': people_data
        })

    except Exception as e:
        logger.error(f"Error getting people for unit {unit_name}: {e}")
        return jsonify({'error': str(e)}), 500

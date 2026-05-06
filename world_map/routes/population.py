"""Population API blueprint."""

from flask import Blueprint, jsonify, request
from collections import defaultdict
import logging

from world_map.utils import convert_numpy_types
from world_map.context import get_app_context

logger = logging.getLogger(__name__)

population_bp = Blueprint('population', __name__)


@population_bp.route('/api/population/statistics')
def get_population_statistics():
    """Get overall population statistics."""
    try:
        world = get_app_context().world
        if not world.population:
            return jsonify({'error': 'No population data'}), 404

        stats = world.population.get_statistics()

        # Add geographical distribution
        geo_distribution = defaultdict(int)
        if world.geography:
            for level in world.geography.levels:
                units = world.geography.get_units_by_level(level)
                for unit in units.values():
                    if unit.people:
                        geo_distribution[level] += len(unit.people)

        stats['geographical_distribution'] = dict(geo_distribution)

        return jsonify(stats)

    except Exception as e:
        logger.error(f"Error getting population statistics: {e}")
        return jsonify({'error': str(e)}), 500


@population_bp.route('/api/population/person/<int:person_id>')
def get_person_details(person_id):
    """Get detailed information about a specific person including activity_map."""
    try:
        world = get_app_context().world
        if not world.population:
            return jsonify({'error': 'No population data'}), 404

        person = world.population.get_person(person_id)
        if not person:
            return jsonify({'error': f'Person {person_id} not found'}), 404

        # Get geographical unit info
        geo_info = None
        if person.geographical_unit:
            geo_info = {
                'id': person.geographical_unit.id,
                'name': person.geographical_unit.name,
                'level': person.geographical_unit.level,
                'coordinates': person.geographical_unit.coordinates
            }

        # Build activity_map representation
        activity_map_data = {}
        if hasattr(person, 'activity_map') and person.activity_map:
            for activity_type, venues_by_type in person.activity_map.items():
                activity_map_data[activity_type] = {}
                if isinstance(venues_by_type, dict):
                    for venue_type, subsets in venues_by_type.items():
                        subset_list = []
                        if subsets:
                            for subset in (subsets if isinstance(subsets, list) else [subsets]):
                                if subset:
                                    subset_info = {
                                        'subset_name': getattr(subset, 'name', 'unknown'),
                                        'venue_id': getattr(subset.venue, 'id', None) if hasattr(subset, 'venue') else None,
                                        'venue_name': getattr(subset.venue, 'name', 'unknown') if hasattr(subset, 'venue') else 'unknown',
                                        'venue_type': getattr(subset.venue, 'type', venue_type) if hasattr(subset, 'venue') else venue_type
                                    }
                                    subset_list.append(subset_info)
                        activity_map_data[activity_type][venue_type] = subset_list

        return jsonify(convert_numpy_types({
            'id': person.id,
            'age': person.age,
            'sex': person.sex,
            'activities': person.activities,
            'activity_map': activity_map_data,
            'properties': person.properties,
            'geographical_unit': geo_info
        }))

    except Exception as e:
        logger.error(f"Error getting person details for {person_id}: {e}")
        return jsonify({'error': str(e)}), 500

"""Population API blueprint."""

from flask import Blueprint, jsonify
import logging

from world_map.utils import convert_numpy_types
from world_map.context import get_app_context

logger = logging.getLogger(__name__)

population_bp = Blueprint('population', __name__)


@population_bp.route('/api/population/statistics')
def get_population_statistics():
    """Get overall population statistics."""
    try:
        loader = get_app_context().record_reader

        stats = loader.compute_population_statistics()
        stats['geographical_distribution'] = loader.compute_geographical_distribution()

        return jsonify(convert_numpy_types(stats))

    except Exception as e:
        logger.error(f"Error getting population statistics: {e}")
        return jsonify({'error': str(e)}), 500


@population_bp.route('/api/population/person/<int:person_id>')
def get_person_details(person_id):
    """Get detailed information about a specific person including activity_map.

    NOTE: the eager slim-mode loader never populated `person.activities`/
    `activity_map`/`properties` (always `[]`/`{}`/`{}`), so this endpoint always
    returned them empty in production — the frontend has dormant rendering code
    for them (app.js ~1105, ~1151). `load_person_slim`/`load_person_activities`
    now supply real data, so this migration activates those code paths rather
    than changing existing behaviour.
    """
    try:
        ctx = get_app_context()
        loader = ctx.record_reader

        person = loader.load_person_slim(person_id)
        if person is None:
            return jsonify({'error': f'Person {person_id} not found'}), 404

        activities = loader.load_person_activities(person_id) or []

        activity_map_data: dict = {}
        for record in activities:
            by_venue_type = activity_map_data.setdefault(record['activity_name'], {})
            by_venue_type.setdefault(record['venue_type'], []).append({
                'subset_name': record['subset_name'],
                'venue_id':    record['venue_id'],
                'venue_name':  record['venue_name'],
                'venue_type':  record['venue_type'],
            })

        return jsonify(convert_numpy_types({
            'id': person['id'],
            'age': person['age'],
            'sex': person['sex'],
            'activities': [record['activity_name'] for record in activities],
            'activity_map': activity_map_data,
            'properties': person['properties'],
            'geographical_unit': person['geographical_unit'],
        }))

    except Exception as e:
        logger.error(f"Error getting person details for {person_id}: {e}")
        return jsonify({'error': str(e)}), 500

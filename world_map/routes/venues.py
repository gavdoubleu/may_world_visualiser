"""Venues, households, and world-statistics API blueprint."""

from flask import Blueprint, jsonify
from collections import defaultdict
import logging

from world_map.utils import convert_numpy_types
from world_map.context import get_app_context

logger = logging.getLogger(__name__)

venues_bp = Blueprint('venues', __name__)


@venues_bp.route('/api/venues/types')
def get_venue_types():
    """Get all available venue types and their counts."""
    try:
        world = get_app_context().world
        if not world.venues:
            return jsonify({'types': []})

        venue_types = {}
        for venue_type in world.venues.get_venue_types():
            venues = world.venues.get_venues_by_type(venue_type)
            venue_types[venue_type] = len(venues)

        return jsonify({'types': venue_types})

    except Exception as e:
        logger.error(f"Error getting venue types: {e}")
        return jsonify({'error': str(e)}), 500


@venues_bp.route('/api/venues/<venue_type>')
def get_venues_by_type(venue_type):
    """Get all venues of a specific type as GeoJSON."""
    try:
        world = get_app_context().world
        if not world.venues:
            return jsonify({'type': 'FeatureCollection', 'features': []})

        venues = world.venues.get_venues_by_type(venue_type)

        features = []
        for venue in venues:
            if not venue.coordinates:
                continue

            lat, lon = venue.coordinates

            # Count members across all subsets
            total_members = 0
            if hasattr(venue, 'subsets') and venue.subsets:
                for subset in venue.subsets.values():
                    if hasattr(subset, 'num_members'):
                        total_members += subset.num_members

            feature = {
                'type': 'Feature',
                'properties': {
                    'id': int(venue.id) if hasattr(venue.id, 'item') else venue.id,
                    'name': str(venue.name),
                    'type': str(venue.type),
                    'geographical_unit': str(venue.geographical_unit.name) if venue.geographical_unit else None,
                    'num_members': int(total_members),
                    'properties': convert_numpy_types(venue.properties) if venue.properties else {}
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

        logger.info(f"Returned {len(features)} venues of type {venue_type}")
        return jsonify(geojson)

    except Exception as e:
        logger.error(f"Error getting venues of type {venue_type}: {e}")
        return jsonify({'error': str(e)}), 500


@venues_bp.route('/api/venues/venue/<int:venue_id>')
def get_venue_details(venue_id):
    """Get detailed information about a specific venue."""
    try:
        ctx = get_app_context()
        world = ctx.world
        if not world.venues:
            return jsonify({'error': 'No venues data'}), 404

        venue = ctx.venue_index.get(venue_id)
        if not venue:
            return jsonify({'error': f'Venue {venue_id} not found'}), 404

        # Get geographical unit info
        geo_info = None
        if venue.geographical_unit:
            geo_info = {
                'id': venue.geographical_unit.id,
                'name': venue.geographical_unit.name,
                'level': venue.geographical_unit.level,
                'coordinates': venue.geographical_unit.coordinates
            }

        # Get subset information
        subsets_info = []
        if hasattr(venue, 'subsets') and venue.subsets:
            for subset_name, subset in venue.subsets.items():
                subset_info = {
                    'name': subset_name,
                }
                if hasattr(subset, 'num_members'):
                    subset_info['num_members'] = subset.num_members
                if hasattr(subset, 'capacity'):
                    subset_info['capacity'] = subset.capacity
                subsets_info.append(subset_info)

        return jsonify({
            'id': venue.id,
            'name': venue.name,
            'type': venue.type,
            'coordinates': venue.coordinates,
            'geographical_unit': geo_info,
            'properties': venue.properties,
            'subsets': subsets_info
        })

    except Exception as e:
        logger.error(f"Error getting venue details for {venue_id}: {e}")
        return jsonify({'error': str(e)}), 500


@venues_bp.route('/api/households/statistics')
def get_household_statistics():
    """Get household statistics."""
    try:
        world = get_app_context().world
        if not world.households:
            return jsonify({'error': 'No household data'}), 404

        total_households = len(world.households.households)

        size_distribution = defaultdict(int)
        for household in world.households.households:
            size = household.size() if hasattr(household, 'size') else len(household.residents)
            size_distribution[size] += 1

        return jsonify({
            'total_households': total_households,
            'size_distribution': dict(size_distribution),
            'average_size': sum(k * v for k, v in size_distribution.items()) / total_households if total_households > 0 else 0
        })

    except Exception as e:
        logger.error(f"Error getting household statistics: {e}")
        return jsonify({'error': str(e)}), 500


@venues_bp.route('/api/world/statistics')
def get_world_statistics():
    """Get comprehensive statistics about the world."""
    try:
        world = get_app_context().world
        stats = world.get_statistics()
        # Merge in slim-mode aggregate statistics if available
        slim_stats = getattr(world, '_slim_statistics', None)
        if slim_stats:
            stats['slim_statistics'] = slim_stats
        stats = convert_numpy_types(stats)
        return jsonify(stats)

    except Exception as e:
        logger.error(f"Error getting world statistics: {e}")
        return jsonify({'error': str(e)}), 500

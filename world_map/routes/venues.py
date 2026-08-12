"""Venues and world-statistics API blueprint."""

from flask import Blueprint, jsonify
import logging

from world_map.utils import convert_numpy_types
from world_map.context import get_app_context
from world_map.geojson import point_feature, feature_collection

logger = logging.getLogger(__name__)

venues_bp = Blueprint('venues', __name__)


@venues_bp.route('/api/venues/types')
def get_venue_types():
    """Get all available venue types and their counts."""
    try:
        types = get_app_context().record_reader.get_venue_type_counts()
        return jsonify({'types': types})

    except Exception as e:
        logger.error(f"Error getting venue types: {e}")
        return jsonify({'error': str(e)}), 500


@venues_bp.route('/api/venues/<venue_type>')
def get_venues_by_type(venue_type):
    """Get all venues of a specific type as GeoJSON."""
    try:
        venues = get_app_context().record_reader.load_venues_by_type(venue_type)

        features = []
        for venue in venues:
            lat, lon = venue['coordinates']
            features.append(point_feature(lat, lon, {
                'id': venue['id'],
                'name': venue['name'],
                'type': venue['type'],
                'geographical_unit': venue['geo_unit'],
                'num_members': venue['num_members'],
                'properties': convert_numpy_types(venue['properties']),
            }))

        geojson = feature_collection(features)
        logger.info(f"Returned {len(features)} venues of type {venue_type}")
        return jsonify(geojson)

    except Exception as e:
        logger.error(f"Error getting venues of type {venue_type}: {e}")
        return jsonify({'error': str(e)}), 500


@venues_bp.route('/api/venues/venue/<int:venue_id>')
def get_venue_details(venue_id):
    """Get detailed information about a specific venue.

    NOTE: `venue_id` here is the RecordReader row index, not the logical
    `venues/ids` value — a known pre-existing world_reader issue (silently
    correct only where venue IDs happen to be contiguous), inherited
    unchanged by this migration. See docs/handoff/fix-venue-id-semantics.md.
    """
    try:
        ctx = get_app_context()
        venue = ctx.record_reader.load_venue_detail(venue_id)
        if venue is None:
            return jsonify({'error': f'Venue {venue_id} not found'}), 404

        geo_info = None
        if venue['geo_unit']:
            unit = ctx.world.geography.get_unit(venue['geo_unit'])
            if unit:
                geo_info = {
                    'id': unit.id,
                    'name': unit.name,
                    'level': unit.level,
                    'coordinates': unit.coordinates,
                }

        return jsonify({
            'id': venue['id'],
            'name': venue['name'],
            'type': venue['type'],
            'coordinates': venue['coordinates'],
            'geographical_unit': geo_info,
            'properties': venue['properties'],
            'subsets': venue['subsets'],
        })

    except Exception as e:
        logger.error(f"Error getting venue details for {venue_id}: {e}")
        return jsonify({'error': str(e)}), 500


@venues_bp.route('/api/world/statistics')
def get_world_statistics():
    """Get comprehensive statistics about the world."""
    try:
        ctx   = get_app_context()
        world = ctx.world

        stats = ctx.record_reader.compute_population_statistics()
        if world.geography:
            stats['total_geo_units'] = len(world.geography.units_by_id)
            stats['geography_levels'] = world.geography.levels
        venue_type_names = ctx.record_reader.get_venue_type_names_present()
        if venue_type_names:
            stats['total_venues'] = int(len(world.venue_types_arr))
            stats['venue_types'] = venue_type_names
            stats['venue_type_counts'] = ctx.record_reader.get_venue_type_counts()

        # Merge in slim-mode aggregate statistics (computed lazily, on first
        # access to this route, since it costs several seconds)
        slim_stats = world.slim_statistics
        if slim_stats:
            stats['slim_statistics'] = slim_stats

        return jsonify(convert_numpy_types(stats))

    except Exception as e:
        logger.error(f"Error getting world statistics: {e}")
        return jsonify({'error': str(e)}), 500

"""Venue/Person browse API blueprint — thin wrappers over world_reader.RecordReader
methods already used by WorldExplorer (load_unit_venues, load_venue_detail,
load_venue_members, load_venue_children, locate_venue, locate_person).

Kept separate from geography.py/venues.py/population.py so each route file
stays focused; see CONTEXT.md (WorldMap, Detail Panel) and
tmp/prds/worldmap-explorer-detail-panel.md for the feature this supports.
"""

from flask import Blueprint, jsonify, request
import logging

from world_map.context import get_app_context

logger = logging.getLogger(__name__)

venue_browse_bp = Blueprint('venue_browse', __name__)


@venue_browse_bp.route('/api/geography/unit/<unit_name>/venues')
def get_unit_venues(unit_name):
    """Paginated top-level venues for a unit's subtree, optionally filtered by type."""
    try:
        ctx = get_app_context()
        world = ctx.world
        if not world.geography:
            return jsonify({'error': 'No geography data'}), 404

        unit = world.geography.get_unit(unit_name)
        if not unit:
            return jsonify({'error': f'Unit {unit_name} not found'}), 404

        venue_type_filter = request.args.get('type')
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 200)

        return jsonify(ctx.record_reader.load_unit_venues(
            unit.id, page, per_page, venue_type_filter))

    except Exception as e:
        logger.error(f"Error getting venues for unit {unit_name}: {e}")
        return jsonify({'error': str(e)}), 500


@venue_browse_bp.route('/api/geography/venue/<int:venue_id>/detail')
def get_venue_detail(venue_id):
    """Full detail for one Venue (name/type/geo_unit/coordinates/properties/subsets)."""
    try:
        venue = get_app_context().record_reader.load_venue_detail(venue_id)
        if venue is None:
            return jsonify({'error': f'Venue {venue_id} not found'}), 404
        return jsonify(venue)
    except Exception as e:
        logger.error(f"Error getting venue detail for {venue_id}: {e}")
        return jsonify({'error': str(e)}), 500


@venue_browse_bp.route('/api/geography/venue/<int:venue_id>/members')
def get_venue_members(venue_id):
    """Paginated Subset member lists for a Venue, optionally filtered to one Subset."""
    try:
        loader = get_app_context().record_reader
        page = max(1, request.args.get('page', 1, type=int))
        per_page = min(request.args.get('per_page', 20, type=int), 200)
        return jsonify(loader.load_venue_members(
            venue_id, page, per_page, request.args.get('subset')))
    except Exception as e:
        logger.error(f"Error getting members for venue {venue_id}: {e}")
        return jsonify({'error': str(e)}), 500


@venue_browse_bp.route('/api/geography/venue/<int:venue_id>/children')
def get_venue_children(venue_id):
    """Paginated ChildVenues for a ParentVenue."""
    try:
        loader = get_app_context().record_reader
        page = max(1, request.args.get('page', 1, type=int))
        per_page = min(request.args.get('per_page', 20, type=int), 200)
        return jsonify(loader.load_venue_children(venue_id, page, per_page))
    except Exception as e:
        logger.error(f"Error getting children for venue {venue_id}: {e}")
        return jsonify({'error': str(e)}), 500


@venue_browse_bp.route('/api/geography/venue/<int:venue_id>/locate')
def locate_venue(venue_id):
    """Resolve the GeoUnit owning a Venue, for the 'go to geo unit' cross-nav action."""
    try:
        per_page = min(request.args.get('per_page', 20, type=int), 200)
        result = get_app_context().record_reader.locate_venue(venue_id, per_page)
        if result is None or result['geo_unit_id'] is None:
            return jsonify({'error': f'Venue {venue_id} not found'}), 404
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error locating venue {venue_id}: {e}")
        return jsonify({'error': str(e)}), 500


@venue_browse_bp.route('/api/geography/person/<int:person_id>/locate')
def locate_person(person_id):
    """Resolve the GeoUnit owning a Person, for the 'go to geo unit' cross-nav action."""
    try:
        per_page = min(request.args.get('per_page', 20, type=int), 200)
        result = get_app_context().record_reader.locate_person(person_id, per_page)
        if result is None or result['geo_unit_id'] is None:
            return jsonify({'error': f'Person {person_id} not found'}), 404
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error locating person {person_id}: {e}")
        return jsonify({'error': str(e)}), 500

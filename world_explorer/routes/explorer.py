"""WorldExplorer core routes: index, theme CSS, geo tree, unit venues, on-demand HDF5 detail."""

import logging
from pathlib import Path

from flask import Blueprint, Response, jsonify, render_template, request, send_from_directory

from world_explorer.context import get_explorer_context
from webapp_utilities.theme_css import render_theme_css
from world_reader.convert import convert_numpy_types

logger = logging.getLogger(__name__)

explorer_bp = Blueprint('explorer', __name__)

_FONTS_DIR  = Path(__file__).parent.parent.parent / 'world_map' / 'static' / 'fonts'
_IMAGES_DIR = Path(__file__).parent.parent / 'images'


@explorer_bp.route('/')
def index():
    return render_template('index.html')


@explorer_bp.route('/theme.css')
def theme_css():
    return Response(render_theme_css(get_explorer_context().theme), mimetype='text/css')


@explorer_bp.route('/wm-fonts/<path:filename>')
def wm_fonts(filename):
    return send_from_directory(_FONTS_DIR, filename)


@explorer_bp.route('/api/explorer/tree')
def get_tree():
    world = get_explorer_context().world
    if not world.geography:
        return jsonify([])

    stats = getattr(world, '_unit_statistics', {}) or {}
    nodes = []
    for uid, unit in world.geography.units_by_id.items():
        unit_stats = stats.get(unit.id)
        nodes.append({
            'id':           int(uid),
            'name':         unit.name,
            'level':        unit.level,
            'parent_id':    int(unit.parent.id) if unit.parent else None,
            'population':   unit_stats.population if unit_stats else 0,
            'venues_count': unit_stats.venues_count if unit_stats else 0,
        })
    return jsonify(nodes)


@explorer_bp.route('/api/explorer/unit/<int:unit_id>')
def get_unit_detail(unit_id):
    """Unit detail built from the explorer's geography + aggregate statistics."""
    world = get_explorer_context().world
    if not world.geography:
        return jsonify({'error': 'No geography data'}), 404

    unit = world.geography.get_unit_by_id(unit_id)
    if not unit:
        return jsonify({'error': f'Unit {unit_id} not found'}), 404

    stats = world._unit_statistics.get(unit_id)
    if stats is None:
        return jsonify({'error': f'No statistics for unit {unit_id}'}), 404

    parent_info = None
    if unit.parent:
        parent_info = {'id': unit.parent.id, 'name': unit.parent.name,
                       'level': unit.parent.level}

    children_info = []
    for child in (unit.children or []):
        child_stats = world._unit_statistics.get(child.id)
        children_info.append({
            'id': child.id, 'name': child.name, 'level': child.level,
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
        'display_name_enabled': False,
        'display_name': None,
    }))


@explorer_bp.route('/api/explorer/unit/<int:unit_id>/people')
def get_unit_people(unit_id):
    ctx = get_explorer_context()
    if not ctx.world.geography:
        return jsonify({'error': 'No geography data'}), 404
    if not ctx.world.geography.get_unit_by_id(unit_id):
        return jsonify({'error': f'Unit {unit_id} not found'}), 404

    page     = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 200)
    return jsonify(ctx.record_reader.load_unit_people(unit_id, page, per_page))


@explorer_bp.route('/api/explorer/unit/<int:unit_id>/venues')
def get_unit_venues(unit_id):
    ctx = get_explorer_context()
    if not ctx.world.geography:
        return jsonify({'error': 'No geography data'}), 404
    if not ctx.world.geography.get_unit_by_id(unit_id):
        return jsonify({'error': f'Unit {unit_id} not found'}), 404

    venue_type_filter = request.args.get('type')
    page     = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 200)
    return jsonify(ctx.record_reader.load_unit_venues(
        unit_id, page, per_page, venue_type_filter))


@explorer_bp.route('/static/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(_IMAGES_DIR, filename)


@explorer_bp.route('/api/explorer/person/<int:person_id>')
def get_person_detail(person_id):
    person = get_explorer_context().record_reader.load_person_slim(person_id)
    if person is None:
        return jsonify({'error': f'Person {person_id} not found'}), 404
    return jsonify(person)


@explorer_bp.route('/api/explorer/person/<int:person_id>/full')
def get_person_full(person_id):
    loader = get_explorer_context().record_reader
    activities = loader.load_person_activities(person_id)
    if activities is None:
        return jsonify({'error': 'Person not found'}), 404
    return jsonify({'activities': activities})


@explorer_bp.route('/api/explorer/venue/<int:venue_id>/detail')
def get_venue_detail(venue_id):
    venue = get_explorer_context().record_reader.load_venue_detail(venue_id)
    if venue is None:
        return jsonify({'error': f'Venue {venue_id} not found'}), 404
    return jsonify(venue)


@explorer_bp.route('/api/explorer/venue/<int:venue_id>/locate')
def locate_venue(venue_id):
    per_page = min(request.args.get('per_page', 20, type=int), 200)
    result   = get_explorer_context().record_reader.locate_venue(venue_id, per_page)
    if result is None or result['geo_unit_id'] is None:
        return jsonify({'error': f'Venue {venue_id} not found'}), 404
    return jsonify(result)


@explorer_bp.route('/api/explorer/person/<int:person_id>/locate')
def locate_person(person_id):
    per_page = min(request.args.get('per_page', 20, type=int), 200)
    result   = get_explorer_context().record_reader.locate_person(person_id, per_page)
    if result is None or result['geo_unit_id'] is None:
        return jsonify({'error': f'Person {person_id} not found'}), 404
    return jsonify(result)


@explorer_bp.route('/api/explorer/venue/<int:venue_id>/children')
def get_venue_children(venue_id):
    loader   = get_explorer_context().record_reader
    per_page = min(request.args.get('per_page', 20, type=int), 200)
    page     = max(1, request.args.get('page', 1, type=int))
    return jsonify(loader.load_venue_children(venue_id, page, per_page))


@explorer_bp.route('/api/explorer/venue/<int:venue_id>/members')
def get_venue_members(venue_id):
    loader   = get_explorer_context().record_reader
    per_page = min(request.args.get('per_page', 20, type=int), 200)
    page     = max(1, request.args.get('page', 1, type=int))
    result   = loader.load_venue_members(venue_id, page, per_page, request.args.get('subset'))
    return jsonify(result)

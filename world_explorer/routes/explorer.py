"""WorldExplorer core routes: index, theme CSS, geo tree, unit venues, on-demand HDF5 detail."""

import logging
from pathlib import Path

import yaml
from flask import Blueprint, Response, jsonify, render_template, request, send_from_directory

from world_explorer.context import get_explorer_context
from world_map.themes.theme_css import build_root_block
from world_map.utils import convert_numpy_types

logger = logging.getLogger(__name__)

explorer_bp = Blueprint('explorer', __name__)

_THEMES_DIR    = Path(__file__).parent.parent.parent / 'world_map' / 'yaml' / 'themes'
_FONTS_DIR     = Path(__file__).parent.parent.parent / 'world_map' / 'static' / 'fonts'
_IMAGES_DIR    = Path(__file__).parent.parent / 'images'
_DEFAULT_THEME = 'dark_scientific'


@explorer_bp.route('/')
def index():
    return render_template('index.html')


@explorer_bp.route('/theme.css')
def theme_css():
    theme_path = _THEMES_DIR / f'{_DEFAULT_THEME}.yaml'
    with open(theme_path) as f:
        theme_config = yaml.safe_load(f) or {}
    css = build_root_block(theme_config)
    return Response(css, mimetype='text/css')


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
        unit_stats = stats.get(unit.name)
        nodes.append({
            'id':           int(uid),
            'name':         unit.name,
            'level':        unit.level,
            'parent_id':    int(unit.parent.id) if unit.parent else None,
            'population':   unit_stats.population if unit_stats else 0,
            'venues_count': unit_stats.venues_count if unit_stats else 0,
        })
    return jsonify(nodes)


@explorer_bp.route('/api/explorer/unit/<unit_name>')
def get_unit_detail(unit_name):
    """Unit detail built from the explorer's geography + aggregate statistics."""
    world = get_explorer_context().world
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
        parent_info = {'id': unit.parent.id, 'name': unit.parent.name,
                       'level': unit.parent.level}

    children_info = []
    for child in (unit.children or []):
        child_stats = world._unit_statistics.get(child.name)
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


@explorer_bp.route('/api/explorer/unit/<unit_name>/people')
def get_unit_people(unit_name):
    ctx = get_explorer_context()
    if not ctx.world.geography:
        return jsonify({'error': 'No geography data'}), 404
    if not ctx.world.geography.get_unit(unit_name):
        return jsonify({'error': f'Unit {unit_name} not found'}), 404

    page     = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 200)
    return jsonify(ctx.explorer_loader.load_unit_people(unit_name, page, per_page))


@explorer_bp.route('/api/explorer/unit/<unit_name>/venues')
def get_unit_venues(unit_name):
    ctx = get_explorer_context()
    if not ctx.world.geography:
        return jsonify({'error': 'No geography data'}), 404
    if not ctx.world.geography.get_unit(unit_name):
        return jsonify({'error': f'Unit {unit_name} not found'}), 404

    venue_type_filter = request.args.get('type')
    page     = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 200)
    return jsonify(ctx.explorer_loader.load_unit_venues(
        unit_name, page, per_page, venue_type_filter))


@explorer_bp.route('/static/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(_IMAGES_DIR, filename)


@explorer_bp.route('/api/explorer/person/<int:person_id>')
def get_person_detail(person_id):
    person = get_explorer_context().explorer_loader.load_person_slim(person_id)
    if person is None:
        return jsonify({'error': f'Person {person_id} not found'}), 404
    return jsonify(person)


@explorer_bp.route('/api/explorer/person/<int:person_id>/full')
def get_person_full(person_id):
    loader = get_explorer_context().explorer_loader
    activities = loader.load_person_activities(person_id)
    if activities is None:
        return jsonify({'error': 'Person not found'}), 404
    return jsonify({'activities': activities})


@explorer_bp.route('/api/explorer/venue/<int:venue_id>/detail')
def get_venue_detail(venue_id):
    venue = get_explorer_context().explorer_loader.load_venue_detail(venue_id)
    if venue is None:
        return jsonify({'error': f'Venue {venue_id} not found'}), 404
    return jsonify(venue)


@explorer_bp.route('/api/explorer/venue/<int:venue_id>/locate')
def locate_venue(venue_id):
    per_page = min(request.args.get('per_page', 20, type=int), 200)
    result   = get_explorer_context().explorer_loader.locate_venue(venue_id, per_page)
    if result is None or result['geo_unit'] is None:
        return jsonify({'error': f'Venue {venue_id} not found'}), 404
    return jsonify(result)


@explorer_bp.route('/api/explorer/person/<int:person_id>/locate')
def locate_person(person_id):
    per_page = min(request.args.get('per_page', 20, type=int), 200)
    result   = get_explorer_context().explorer_loader.locate_person(person_id, per_page)
    if result is None or result['geo_unit'] is None:
        return jsonify({'error': f'Person {person_id} not found'}), 404
    return jsonify(result)


@explorer_bp.route('/api/explorer/venue/<int:venue_id>/members')
def get_venue_members(venue_id):
    loader   = get_explorer_context().explorer_loader
    per_page = min(request.args.get('per_page', 20, type=int), 200)
    page     = max(1, request.args.get('page', 1, type=int))
    result   = loader.load_venue_members(venue_id, page, per_page, request.args.get('subset'))
    return jsonify(result)

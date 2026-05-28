"""WorldExplorer core routes: index, theme CSS, geo tree, unit venues, on-demand HDF5 detail."""

import logging
from pathlib import Path

import yaml
from flask import Blueprint, Response, jsonify, render_template, request, send_from_directory

from world_explorer.context import get_explorer_context
from world_map.themes.theme_css import build_root_block

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


@explorer_bp.route('/api/explorer/unit/<unit_name>/venues')
def get_unit_venues(unit_name):
    world = get_explorer_context().world
    if not world.geography:
        return jsonify({'error': 'No geography data'}), 404

    unit = world.geography.get_unit(unit_name)
    if not unit:
        return jsonify({'error': f'Unit {unit_name} not found'}), 404

    venue_type_filter = request.args.get('type')
    page     = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)

    def collect_venues(u):
        result = list(u.venues)
        for child in u.children:
            result.extend(collect_venues(child))
        return result

    all_venues = collect_venues(unit)
    if venue_type_filter:
        all_venues = [v for v in all_venues if v.type == venue_type_filter]

    total_count = len(all_venues)
    start       = (page - 1) * per_page
    page_venues = all_venues[start:start + per_page]

    return jsonify({
        'unit_name':   unit_name,
        'venue_type':  venue_type_filter,
        'total_count': total_count,
        'page':        page,
        'per_page':    per_page,
        'total_pages': max(1, (total_count + per_page - 1) // per_page),
        'venues': [
            {
                'id':          v.id,
                'name':        v.name,
                'type':        v.type,
                'coordinates': v.coordinates,
                'properties':  v.properties or {},
                'subsets': [
                    {'name': s_name, 'num_members': s.num_members}
                    for s_name, s in (v.subsets.items() if hasattr(v, 'subsets') else [])
                ],
            }
            for v in page_venues
        ],
    })


@explorer_bp.route('/static/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(_IMAGES_DIR, filename)


@explorer_bp.route('/api/explorer/person/<int:person_id>/full')
def get_person_full(person_id):
    loader = get_explorer_context().explorer_loader
    activities = loader.load_person_activities(person_id)
    if activities is None:
        return jsonify({'error': 'Person not found'}), 404
    return jsonify({'activities': activities})


@explorer_bp.route('/api/explorer/venue/<int:venue_id>/detail')
def get_venue_detail(venue_id):
    world = get_explorer_context().world
    all_venues = world.venues.get_all_venues()
    venue = all_venues.get(venue_id)
    if not venue:
        return jsonify({'error': f'Venue {venue_id} not found'}), 404
    geo_unit = venue.geographical_unit
    return jsonify({
        'id':          venue.id,
        'name':        venue.name,
        'type':        venue.type,
        'geo_unit':    geo_unit.name if geo_unit else None,
        'coordinates': venue.coordinates,
        'properties':  venue.properties or {},
        'subsets': [
            {'name': s_name, 'num_members': s.num_members}
            for s_name, s in venue.subsets.items()
        ],
    })


@explorer_bp.route('/api/explorer/venue/<int:venue_id>/members')
def get_venue_members(venue_id):
    loader   = get_explorer_context().explorer_loader
    per_page = min(request.args.get('per_page', 50, type=int), 200)
    page     = max(1, request.args.get('page', 1, type=int))
    result   = loader.load_venue_members(venue_id, page, per_page, request.args.get('subset'))
    return jsonify(result)

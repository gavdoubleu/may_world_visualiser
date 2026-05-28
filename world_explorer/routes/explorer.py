"""WorldExplorer core routes: index, theme CSS, geo tree, unit venues, on-demand HDF5 detail."""

import logging
from pathlib import Path

import h5py
import numpy as np
import yaml
from flask import Blueprint, Response, current_app, jsonify, render_template, request, send_from_directory

from world_map.context import get_app_context
from world_map.themes.theme_css import build_root_block

logger = logging.getLogger(__name__)

explorer_bp = Blueprint('explorer', __name__)

_THEMES_DIR  = Path(__file__).parent.parent.parent / 'world_map' / 'yaml' / 'themes'
_FONTS_DIR   = Path(__file__).parent.parent.parent / 'world_map' / 'static' / 'fonts'
_IMAGES_DIR  = Path(__file__).parent.parent / 'images'
_DEFAULT_THEME = 'dark_scientific'

_SEX_DECODE = {0: 'male', 1: 'female', 2: 'unknown'}


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
    world = get_app_context().world
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
    world = get_app_context().world
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
    """Return full activity map for a person, read on-demand from HDF5."""
    person_id_to_idx = current_app.config.get('PERSON_ID_TO_IDX')
    hdf5_path        = current_app.config.get('HDF5_PATH')
    subset_venue_ids = current_app.config.get('SUBSET_VENUE_IDS')
    world            = get_app_context().world

    if person_id_to_idx is None or person_id < 0 or person_id >= len(person_id_to_idx):
        return jsonify({'error': 'Person not found'}), 404

    person_array_idx = int(person_id_to_idx[person_id])

    with h5py.File(hdf5_path, 'r') as f:
        offsets   = f['activity_mappings/activity_map/activity_offsets']
        n_people  = len(offsets)
        start     = int(offsets[person_array_idx])
        end       = (int(offsets[person_array_idx + 1])
                     if person_array_idx + 1 < n_people
                     else int(f['activity_mappings/activity_map/activity_data'].shape[0]))

        if start >= end:
            return jsonify({'activities': []})

        act_data      = f['activity_mappings/activity_map/activity_data'][start:end]
        act_names     = f['activity_mappings/activity_map/activity_names'][:]
        venue_names   = f['metadata/names/venues']
        subset_names  = f['metadata/names/subsets']
        venue_types   = f['venues/types']
        venue_type_names = [n.decode() if isinstance(n, bytes) else str(n)
                            for n in f['metadata/registries/venue_types'][:]]
        venue_geo_ids = f['venues/geo_unit_ids']

        activities = []
        for row in act_data:
            act_type_idx = int(row[1])
            venue_id     = int(row[2])
            subset_pos   = int(row[3])

            act_name = (act_names[act_type_idx].decode()
                        if isinstance(act_names[act_type_idx], bytes)
                        else str(act_names[act_type_idx]))

            raw_vname  = venue_names[venue_id]
            venue_name = raw_vname.decode() if isinstance(raw_vname, bytes) else str(raw_vname)

            vtype_idx  = int(venue_types[venue_id])
            venue_type = venue_type_names[vtype_idx] if vtype_idx < len(venue_type_names) else 'unknown'

            # Venue geo unit name
            venue_geo_id = int(venue_geo_ids[venue_id])
            venue_unit   = world.geography.units_by_id.get(venue_geo_id)
            venue_geo_unit = venue_unit.name if venue_unit else str(venue_geo_id)

            # Subset name via searchsorted on pre-loaded subset_venue_ids
            first_sub = int(np.searchsorted(subset_venue_ids, venue_id, side='left'))
            last_sub  = int(np.searchsorted(subset_venue_ids, venue_id, side='right'))
            if first_sub < last_sub:
                subset_row = first_sub + subset_pos
                raw_sname  = subset_names[subset_row]
                subset_name = raw_sname.decode() if isinstance(raw_sname, bytes) else str(raw_sname)
            else:
                subset_name = str(subset_pos)

            activities.append({
                'activity_name': act_name,
                'venue_id':      venue_id,
                'venue_name':    venue_name,
                'venue_type':    venue_type,
                'venue_geo_unit': venue_geo_unit,
                'subset_name':   subset_name,
            })

    return jsonify({'activities': activities})


@explorer_bp.route('/api/explorer/venue/<int:venue_id>/members')
def get_venue_members(venue_id):
    """Return subset member lists for a venue, read on-demand from HDF5."""
    hdf5_path        = current_app.config.get('HDF5_PATH')
    subset_venue_ids = current_app.config.get('SUBSET_VENUE_IDS')
    person_id_to_idx = current_app.config.get('PERSON_ID_TO_IDX')
    world            = get_app_context().world

    per_page          = min(request.args.get('per_page', 50, type=int), 200)
    subset_name_filter = request.args.get('subset')
    page              = max(1, request.args.get('page', 1, type=int))

    first_sub = int(np.searchsorted(subset_venue_ids, venue_id, side='left'))
    last_sub  = int(np.searchsorted(subset_venue_ids, venue_id, side='right'))

    if first_sub >= last_sub:
        return jsonify({'venue_id': venue_id, 'venue_name': str(venue_id), 'subsets': []})

    with h5py.File(hdf5_path, 'r') as f:
        venue_name_raw = f['metadata/names/venues'][venue_id]
        venue_name     = venue_name_raw.decode() if isinstance(venue_name_raw, bytes) else str(venue_name_raw)

        subset_names_arr = f['metadata/names/subsets']
        members_offsets  = f['venues/subsets/members_offsets']
        members_flat     = f['venues/subsets/members_flat']
        n_subsets        = len(members_offsets)
        n_members_flat   = len(members_flat)

        pop_ids      = f['population/ids']
        pop_ages     = f['population/ages']
        pop_sexes    = f['population/sexes']
        pop_geo_ids  = f['population/geo_unit_ids']

        result_subsets = []
        for subset_row in range(first_sub, last_sub):
            raw_sname   = subset_names_arr[subset_row]
            sname       = raw_sname.decode() if isinstance(raw_sname, bytes) else str(raw_sname)

            if subset_name_filter and sname != subset_name_filter:
                continue

            ms = int(members_offsets[subset_row])
            me = (int(members_offsets[subset_row + 1])
                  if subset_row + 1 < n_subsets
                  else n_members_flat)

            total      = me - ms
            page_start = ms + (page - 1) * per_page
            page_end   = min(ms + page * per_page, me)

            if page_start >= me:
                result_subsets.append({
                    'name': sname, 'total': total, 'page': page,
                    'per_page': per_page,
                    'total_pages': max(1, (total + per_page - 1) // per_page),
                    'members': [],
                })
                continue

            page_idxs  = np.array(members_flat[page_start:page_end], dtype=np.int64)
            array_idxs = person_id_to_idx[page_idxs]  # person IDs → array positions
            sort_order = np.argsort(array_idxs)
            sorted_idxs = array_idxs[sort_order]
            idx_list   = sorted_idxs.tolist()

            ids_b    = pop_ids[idx_list]
            ages_b   = pop_ages[idx_list]
            sexes_b  = pop_sexes[idx_list]
            geo_b    = pop_geo_ids[idx_list]

            unsort   = np.argsort(sort_order)
            ids_b    = ids_b[unsort]
            ages_b   = ages_b[unsort]
            sexes_b  = sexes_b[unsort]
            geo_b    = geo_b[unsort]

            members = []
            for ids_val, age_val, sex_val, geo_id_val in zip(ids_b, ages_b, sexes_b, geo_b):
                geo_unit = world.geography.units_by_id.get(int(geo_id_val))
                members.append({
                    'id':       int(ids_val),
                    'age':      int(age_val),
                    'sex':      _SEX_DECODE.get(int(sex_val), 'unknown'),
                    'geo_unit': geo_unit.name if geo_unit else str(int(geo_id_val)),
                })

            result_subsets.append({
                'name':        sname,
                'total':       total,
                'page':        page,
                'per_page':    per_page,
                'total_pages': max(1, (total + per_page - 1) // per_page),
                'members':     members,
            })

    return jsonify({
        'venue_id':   venue_id,
        'venue_name': venue_name,
        'subsets':    result_subsets,
    })

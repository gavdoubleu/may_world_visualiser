"""On-demand HDF5 record reads, shared by WorldMap and WorldExplorer."""

import h5py
import numpy as np

from world_reader.convert import SEX_DECODE, decode_str
from world_reader.id_index import IdIndex
from world_reader.pagination import calc_total_pages
from world_reader.statistics import (
    compute_population_statistics as _compute_population_statistics,
    compute_geographical_distribution as _compute_geographical_distribution,
)


class RecordReader:
    """All per-request HDF5 reads, wired to a resident WorldStore for indices."""

    def __init__(self, hdf5_path, store):
        self._hdf5_path = str(hdf5_path)
        self._person_id_to_idx    = store.person_id_to_idx
        self._subset_venue_ids    = store.subset_venue_ids
        self._venue_ids           = store.venue_ids
        self._venue_id_to_idx     = store.venue_id_to_idx
        self._geography           = store.geography
        self._subtree_index       = store.subtree_index
        self._person_geo_unit_ids = store.person_geo_unit_ids
        self._venue_geo_unit_ids  = store.venue_geo_unit_ids
        self._venue_types_arr     = store.venue_types_arr
        self._venue_type_names_cache = store.venue_type_names or []
        self._venue_list_position = store.venue_list_position
        self._person_list_position = store.person_list_position
        self._venue_parent_ids           = store.venue_parent_ids
        self._venue_child_counts         = store.venue_child_counts
        self._venue_child_total_members  = store.venue_child_total_members
        self._children_by_parent_sorted  = store.children_by_parent_sorted
        self._children_parent_ids_sorted = store.children_parent_ids_sorted

    def load_person_activities(self, person_id: int) -> list[dict] | None:
        """Return ActivityMap records for person_id, or None if not found."""
        if self._person_id_to_idx is None:
            return None
        person_array_idx = int(self._person_id_to_idx[person_id])
        if person_array_idx == IdIndex.MISSING:
            return None

        with h5py.File(self._hdf5_path, 'r') as f:
            offsets  = f['activity_mappings/activity_map/activity_offsets']
            n_people = len(offsets)
            start    = int(offsets[person_array_idx])
            end      = (int(offsets[person_array_idx + 1])
                        if person_array_idx + 1 < n_people
                        else int(f['activity_mappings/activity_map/activity_data'].shape[0]))

            if start >= end:
                return []

            act_data         = f['activity_mappings/activity_map/activity_data'][start:end]
            act_names        = f['activity_mappings/activity_map/activity_names'][:]
            venue_names      = f['metadata/names/venues']
            subset_names     = f['metadata/names/subsets']
            venue_types      = f['venues/types']
            venue_type_names = [decode_str(n) for n in f['metadata/registries/venue_types'][:]]
            venue_geo_ids    = f['venues/geo_unit_ids']

            activities = []
            for row in act_data:
                act_type_idx = int(row[1])
                venue_id     = int(row[2])
                subset_pos   = int(row[3])

                act_name   = decode_str(act_names[act_type_idx])
                venue_name = decode_str(venue_names[venue_id])
                vtype_idx  = int(venue_types[venue_id])
                venue_type = venue_type_names[vtype_idx] if vtype_idx < len(venue_type_names) else 'unknown'

                venue_geo_id  = int(venue_geo_ids[venue_id])
                venue_unit    = self._geography.units_by_id.get(venue_geo_id)
                venue_geo_unit = venue_unit.name if venue_unit else str(venue_geo_id)

                first_sub = int(np.searchsorted(self._subset_venue_ids, venue_id, side='left'))
                last_sub  = int(np.searchsorted(self._subset_venue_ids, venue_id, side='right'))
                if first_sub < last_sub:
                    subset_row  = first_sub + subset_pos
                    subset_name = decode_str(subset_names[subset_row])
                else:
                    subset_name = str(subset_pos)

                activities.append({
                    'activity_name':  act_name,
                    'venue_id':       venue_id,
                    'venue_name':     venue_name,
                    'venue_type':     venue_type,
                    'venue_geo_unit': venue_geo_unit,
                    'subset_name':    subset_name,
                })

        return activities

    def load_venue_members(self, venue_id: int, page: int, per_page: int,
                           subset_filter: str | None) -> dict:
        """Return paginated Subset member lists for a Venue (venue_id is logical)."""
        row = int(self._venue_id_to_idx[venue_id])
        if row == IdIndex.MISSING:
            return {'venue_id': venue_id, 'venue_name': str(venue_id), 'subsets': []}

        first_sub = int(np.searchsorted(self._subset_venue_ids, row, side='left'))
        last_sub  = int(np.searchsorted(self._subset_venue_ids, row, side='right'))

        if first_sub >= last_sub:
            return {'venue_id': venue_id, 'venue_name': str(venue_id), 'subsets': []}

        with h5py.File(self._hdf5_path, 'r') as f:
            venue_name       = decode_str(f['metadata/names/venues'][row])
            subset_names_arr = f['metadata/names/subsets']
            members_offsets  = f['venues/subsets/members_offsets']
            members_flat     = f['venues/subsets/members_flat']
            n_subsets        = len(members_offsets)
            n_members_flat   = len(members_flat)

            pop_ids     = f['population/ids']
            pop_ages    = f['population/ages']
            pop_sexes   = f['population/sexes']
            pop_geo_ids = f['population/geo_unit_ids']

            result_subsets = []
            for subset_row in range(first_sub, last_sub):
                sname = decode_str(subset_names_arr[subset_row])

                if subset_filter and sname != subset_filter:
                    continue

                ms    = int(members_offsets[subset_row])
                me    = (int(members_offsets[subset_row + 1])
                         if subset_row + 1 < n_subsets
                         else n_members_flat)
                total = me - ms

                page_start = ms + (page - 1) * per_page
                page_end   = min(ms + page * per_page, me)

                if page_start >= me:
                    result_subsets.append({
                        'name': sname, 'total': total, 'page': page,
                        'per_page': per_page,
                        'total_pages': calc_total_pages(total, per_page),
                        'members': [],
                    })
                    continue

                page_idxs   = np.array(members_flat[page_start:page_end], dtype=np.int64)
                array_idxs  = self._person_id_to_idx[page_idxs]
                sort_order  = np.argsort(array_idxs)
                sorted_idxs = array_idxs[sort_order]
                idx_list    = sorted_idxs.tolist()

                ids_b   = pop_ids[idx_list]
                ages_b  = pop_ages[idx_list]
                sexes_b = pop_sexes[idx_list]
                geo_b   = pop_geo_ids[idx_list]

                unsort  = np.argsort(sort_order)
                ids_b   = ids_b[unsort]
                ages_b  = ages_b[unsort]
                sexes_b = sexes_b[unsort]
                geo_b   = geo_b[unsort]

                members = []
                for id_val, age_val, sex_val, geo_id_val in zip(ids_b, ages_b, sexes_b, geo_b):
                    geo_unit = self._geography.units_by_id.get(int(geo_id_val))
                    members.append({
                        'id':       int(id_val),
                        'age':      int(age_val),
                        'sex':      SEX_DECODE.get(int(sex_val), 'unknown'),
                        'geo_unit': geo_unit.name if geo_unit else str(int(geo_id_val)),
                    })

                result_subsets.append({
                    'name':        sname,
                    'total':       total,
                    'page':        page,
                    'per_page':    per_page,
                    'total_pages': calc_total_pages(total, per_page),
                    'members':     members,
                })

        return {'venue_id': venue_id, 'venue_name': venue_name, 'subsets': result_subsets}

    # ── whole-world aggregate reads ──────────────────────────────────────────

    def compute_population_statistics(self) -> dict:
        """Population-wide total/age/sex aggregates (see world_reader.statistics)."""
        with h5py.File(self._hdf5_path, 'r') as f:
            return _compute_population_statistics(f)

    def compute_geographical_distribution(self) -> dict:
        """Per-level counts of people by their direct geo unit."""
        return _compute_geographical_distribution(self._person_geo_unit_ids, self._geography)

    # ── slim detail / list reads (no in-memory Person/Venue objects) ─────────────

    def load_person_slim(self, person_id: int) -> dict | None:
        """Return {id, age, sex, geographical_unit, properties} for one person.

        Activities are loaded separately via load_person_activities — matching the
        slim-mode person panel, which lazily fetches activities on demand.
        """
        if self._person_id_to_idx is None:
            return None
        array_idx = int(self._person_id_to_idx[person_id])
        if array_idx == IdIndex.MISSING:
            return None

        with h5py.File(self._hdf5_path, 'r') as f:
            age    = int(f['population/ages'][array_idx])
            sex    = SEX_DECODE.get(int(f['population/sexes'][array_idx]), 'unknown')
            geo_id = int(f['population/geo_unit_ids'][array_idx])

            properties = {}
            if 'population/properties' in f:
                for key in f['population/properties']:
                    properties[key] = decode_str(f[f'population/properties/{key}'][array_idx])

        unit = self._geography.units_by_id.get(geo_id)
        geo_info = None
        if unit:
            geo_info = {
                'id': unit.id, 'name': unit.name, 'level': unit.level,
                'coordinates': unit.coordinates,
            }

        return {
            'id': person_id, 'age': age, 'sex': sex,
            'activities': [], 'activity_map': {},
            'properties': properties, 'geographical_unit': geo_info,
        }

    def load_unit_people(self, unit_name: str, page: int, per_page: int) -> dict:
        """Paginated id/age/sex for the unit's whole subtree, via SubtreeIndex."""
        unit = self._geography.get_unit(unit_name)
        if unit is None or self._subtree_index is None:
            return {'unit_name': unit_name, 'total_count': 0, 'page': page,
                    'per_page': per_page, 'total_pages': 0, 'people': []}

        rows  = np.sort(self._subtree_index.person_rows(unit.id))
        total = int(len(rows))
        page_rows = rows[(page - 1) * per_page: page * per_page]

        people = []
        if len(page_rows):
            idx = page_rows.tolist()  # ascending → valid h5py fancy index
            with h5py.File(self._hdf5_path, 'r') as f:
                ids   = f['population/ids'][idx]
                ages  = f['population/ages'][idx]
                sexes = f['population/sexes'][idx]
            for id_val, age_val, sex_val in zip(ids, ages, sexes):
                people.append({
                    'id': int(id_val), 'age': int(age_val),
                    'sex': SEX_DECODE.get(int(sex_val), 'unknown'),
                    'activities': [], 'primary_activity': None,
                })

        return {
            'unit_name': unit_name, 'total_count': total, 'page': page,
            'per_page': per_page, 'total_pages': calc_total_pages(total, per_page),
            'people': people,
        }

    def load_unit_venues(self, unit_name: str, page: int, per_page: int,
                         type_filter: str | None) -> dict:
        """Paginated venues for the unit's subtree, via SubtreeIndex."""
        unit = self._geography.get_unit(unit_name)
        if unit is None or self._subtree_index is None:
            return {'unit_name': unit_name, 'venue_type': type_filter, 'total_count': 0,
                    'page': page, 'per_page': per_page, 'total_pages': 0, 'venues': []}

        rows = np.sort(self._subtree_index.venue_rows(unit.id))

        with h5py.File(self._hdf5_path, 'r') as f:
            type_names = self._venue_type_names(f)

            if type_filter and len(rows):
                row_types = f['venues/types'][:][rows]
                keep = np.array(
                    [type_names[int(t)] if int(t) < len(type_names) else 'unknown'
                     for t in row_types]) == type_filter
                rows = rows[keep]

            # exclude ChildVenues from top-level list
            if self._venue_parent_ids is not None and len(rows):
                top_level_mask = self._venue_parent_ids[rows] == -1
                rows = rows[top_level_mask]

            total = int(len(rows))
            page_rows = rows[(page - 1) * per_page: page * per_page]

            venues = []
            if len(page_rows):
                idx        = page_rows.tolist()  # ascending → valid h5py fancy index
                names      = f['metadata/names/venues'][idx]
                types      = f['venues/types'][idx]
                lats       = f['venues/latitudes'][idx]
                lons       = f['venues/longitudes'][idx]
                geo_ids    = f['venues/geo_unit_ids'][idx]
                for venue_id, name_b, type_code, lat, lon, geo_id in zip(
                        idx, names, types, lats, lons, geo_ids):
                    child_count = (int(self._venue_child_counts[venue_id])
                                   if self._venue_child_counts is not None else 0)
                    total_child_members = (int(self._venue_child_total_members[venue_id])
                                           if self._venue_child_total_members is not None
                                           else 0)
                    venues.append({
                        'id': int(self._venue_ids[venue_id]),
                        'name': decode_str(name_b),
                        'type': (type_names[int(type_code)]
                                 if int(type_code) < len(type_names) else 'unknown'),
                        'coordinates': (None if np.isnan(lat)
                                        else [float(lat), float(lon)]),
                        'properties': self._venue_properties(f, int(venue_id)),
                        'geo_unit': self._unit_name(int(geo_id)),
                        'subsets': self._venue_subsets(f, int(venue_id)),
                        'child_count': child_count,
                        'total_child_members': total_child_members,
                    })

        return {
            'unit_name': unit_name, 'venue_type': type_filter, 'total_count': total,
            'page': page, 'per_page': per_page,
            'total_pages': calc_total_pages(total, per_page), 'venues': venues,
        }

    def load_venues_by_type(self, venue_type: str) -> list[dict]:
        """All venues of `venue_type` with coordinates, as map-ready rows:
        {id, name, type, geo_unit, coordinates, num_members, properties}.
        Bulk array read — no per-venue Python objects."""
        if (self._venue_types_arr is None
                or venue_type not in self._venue_type_names_cache):
            return []
        type_code = self._venue_type_names_cache.index(venue_type)
        rows = np.where(self._venue_types_arr == type_code)[0]
        if not len(rows):
            return []

        venues = []
        with h5py.File(self._hdf5_path, 'r') as f:
            idx     = rows.tolist()
            names   = f['metadata/names/venues'][idx]
            lats    = f['venues/latitudes'][idx]
            lons    = f['venues/longitudes'][idx]
            geo_ids = f['venues/geo_unit_ids'][idx]
            for venue_id, name_b, lat, lon, geo_id in zip(
                    idx, names, lats, lons, geo_ids):
                if np.isnan(lat):
                    continue
                subsets = self._venue_subsets(f, int(venue_id))
                venues.append({
                    'id': int(self._venue_ids[venue_id]),
                    'name': decode_str(name_b),
                    'type': venue_type,
                    'geo_unit': self._unit_name(int(geo_id)),
                    'coordinates': [float(lat), float(lon)],
                    'num_members': sum(s['num_members'] for s in subsets),
                    'properties': self._venue_properties(f, int(venue_id)),
                })
        return venues

    def load_venue_detail(self, venue_id: int) -> dict | None:
        """Single venue detail by logical venue ID (venues/ids), plus its subsets."""
        row = int(self._venue_id_to_idx[venue_id])
        if row == IdIndex.MISSING:
            return None
        with h5py.File(self._hdf5_path, 'r') as f:
            type_names = self._venue_type_names(f)
            type_code  = int(f['venues/types'][row])
            lat        = float(f['venues/latitudes'][row])
            lon        = float(f['venues/longitudes'][row])
            geo_id     = int(f['venues/geo_unit_ids'][row])
            return {
                'id': int(self._venue_ids[row]),
                'name': decode_str(f['metadata/names/venues'][row]),
                'type': (type_names[type_code]
                         if type_code < len(type_names) else 'unknown'),
                'geo_unit': self._unit_name(geo_id),
                'coordinates': (None if np.isnan(lat) else [lat, lon]),
                'properties': self._venue_properties(f, row),
                'subsets': self._venue_subsets(f, row),
            }

    def load_venue_children(self, venue_id: int, page: int, per_page: int) -> dict:
        """Return paginated ChildVenues for a ParentVenue."""
        empty = {'parent_id': venue_id, 'total_count': 0, 'page': page,
                 'per_page': per_page, 'total_pages': 0, 'venues': []}

        if (self._children_by_parent_sorted is None
                or self._children_parent_ids_sorted is None):
            return empty

        parent_row = int(self._venue_id_to_idx[venue_id])
        if parent_row == IdIndex.MISSING:
            return empty

        first = int(np.searchsorted(self._children_parent_ids_sorted, parent_row, side='left'))
        last  = int(np.searchsorted(self._children_parent_ids_sorted, parent_row, side='right'))
        if first >= last:
            return empty

        all_child_rows = self._children_by_parent_sorted[first:last]
        total = int(len(all_child_rows))
        page_rows = all_child_rows[(page - 1) * per_page: page * per_page]

        venues = []
        if len(page_rows):
            with h5py.File(self._hdf5_path, 'r') as f:
                type_names = self._venue_type_names(f)
                idx     = sorted(page_rows.tolist())
                names   = f['metadata/names/venues'][idx]
                types   = f['venues/types'][idx]
                lats    = f['venues/latitudes'][idx]
                lons    = f['venues/longitudes'][idx]
                geo_ids = f['venues/geo_unit_ids'][idx]
                for venue_row, name_b, type_code, lat, lon, geo_id in zip(
                        idx, names, types, lats, lons, geo_ids):
                    venues.append({
                        'id': int(self._venue_ids[venue_row]),
                        'name': decode_str(name_b),
                        'type': (type_names[int(type_code)]
                                 if int(type_code) < len(type_names) else 'unknown'),
                        'coordinates': (None if np.isnan(lat) else [float(lat), float(lon)]),
                        'properties': self._venue_properties(f, int(venue_row)),
                        'geo_unit': self._unit_name(int(geo_id)),
                        'subsets': self._venue_subsets(f, int(venue_row)),
                        'child_count': 0,
                        'total_child_members': 0,
                    })

        return {
            'parent_id':   venue_id,
            'total_count': total,
            'page':        page,
            'per_page':    per_page,
            'total_pages': calc_total_pages(total, per_page),
            'venues':      venues,
        }

    # ── locate (O(1) page lookup from startup position arrays) ───────────────────

    def locate_venue(self, venue_id: int, per_page: int) -> dict | None:
        """Return {geo_unit, venue_type, page} for venue_id, or None if invalid."""
        if self._venue_geo_unit_ids is None or self._venue_id_to_idx is None:
            return None
        row = int(self._venue_id_to_idx[venue_id])
        if row == IdIndex.MISSING:
            return None
        geo_id     = int(self._venue_geo_unit_ids[row])
        unit       = self._geography.units_by_id.get(geo_id)
        type_code  = int(self._venue_types_arr[row])
        venue_type = (self._venue_type_names_cache[type_code]
                      if type_code < len(self._venue_type_names_cache) else 'unknown')
        position   = int(self._venue_list_position[row])
        return {
            'geo_unit':   unit.name if unit else None,
            'venue_type': venue_type,
            'page':       position // per_page + 1,
        }

    def locate_person(self, person_id: int, per_page: int) -> dict | None:
        """Return {geo_unit, page} for person_id, or None if invalid."""
        if self._person_geo_unit_ids is None or self._person_id_to_idx is None:
            return None
        array_idx = int(self._person_id_to_idx[person_id])
        if array_idx == IdIndex.MISSING:
            return None
        geo_id    = int(self._person_geo_unit_ids[array_idx])
        unit      = self._geography.units_by_id.get(geo_id)
        position  = int(self._person_list_position[array_idx])
        return {
            'geo_unit': unit.name if unit else None,
            'page':     position // per_page + 1,
        }

    # ── small helpers ────────────────────────────────────────────────────────────

    def _venue_subsets(self, f, venue_id: int) -> list[dict]:
        """[{name, num_members}] for a venue, from the sorted subset_venue_ids index."""
        first = int(np.searchsorted(self._subset_venue_ids, venue_id, side='left'))
        last  = int(np.searchsorted(self._subset_venue_ids, venue_id, side='right'))
        if first >= last:
            return []
        names   = f['metadata/names/subsets'][first:last]
        counts  = f['venues/subsets/member_counts'][first:last]
        return [{'name': decode_str(n), 'num_members': int(c)}
                for n, c in zip(names, counts)]

    @staticmethod
    def _venue_properties(f, venue_id: int) -> dict:
        """{'is_residence': bool} for a venue, mirroring the eager loader's
        slim-mode properties (the only venue property it ever populated)."""
        properties = {}
        if 'venues/is_residence' in f:
            properties['is_residence'] = bool(f['venues/is_residence'][venue_id])
        return properties

    def _unit_name(self, geo_id: int) -> str | None:
        unit = self._geography.units_by_id.get(geo_id)
        return unit.name if unit else None

    @staticmethod
    def _venue_type_names(f) -> list[str]:
        if 'metadata/registries/venue_types' in f:
            return [decode_str(n)
                    for n in f['metadata/registries/venue_types'][:]]
        return []

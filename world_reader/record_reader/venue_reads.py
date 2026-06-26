"""Venue-domain reads for RecordReader."""

import h5py
import numpy as np
import pandas as pd

from world_reader.convert import SEX_DECODE, decode_str
from world_reader.id_index import IdIndex
from world_reader.pagination import calc_total_pages


class _VenueReads:
    """Mixin: assumes attributes set by RecordReader.__init__ (core.py)."""

    def load_venue_members(self, venue_id: int, page: int, per_page: int,
                           subset_filter: str | None) -> dict:
        """Paginated Subset member lists for a Venue.

        Each Subset is paginated independently — `page`/`per_page` apply to
        every Subset's member list, not to a flattened combined list.

        Args:
            venue_id: Logical venue ID.
            page: 1-indexed page number, applied per Subset.
            per_page: Page size, applied per Subset.
            subset_filter: If given, only include the Subset with this name.

        Returns:
            `{venue_id, venue_name, subsets}`, where each subset is
            `{name, total, page, per_page, total_pages, members}` and each
            member is `{id, age, sex, geo_unit}`. `subsets` is empty if
            `venue_id` is unknown or has no subsets.
        """
        row = int(self._venue_id_to_idx[venue_id])
        if row == IdIndex.MISSING:
            return {'venue_id': venue_id, 'venue_name': str(venue_id), 'subsets': []}

        first_sub = int(np.searchsorted(self._subset_venue_ids, row, side='left'))
        last_sub  = int(np.searchsorted(self._subset_venue_ids, row, side='right'))

        if first_sub >= last_sub:
            return {'venue_id': venue_id, 'venue_name': str(venue_id), 'subsets': []}

        with h5py.File(self._hdf5_path, 'r') as f:
            venue_name      = decode_str(f['metadata/names/venues'][row])
            # contiguous slice — first_sub:last_sub is one venue's own subset
            # block, so no fancy-indexing/ordering concern here.
            subset_names    = pd.Series(
                f['metadata/names/subsets'][first_sub:last_sub]).str.decode('utf-8').tolist()
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
                sname = subset_names[subset_row - first_sub]

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

    def load_unit_venues(self, unit_id: int, page: int, per_page: int,
                         type_filter: str | None) -> dict:
        """Paginated top-level venues for a GeoUnit's whole subtree, via SubtreeIndex.

        ChildVenues are excluded — they're only reachable via
        `load_venue_children` on their ParentVenue.

        Args:
            unit_id: GeoUnit ID whose subtree to list.
            page: 1-indexed page number.
            per_page: Page size.
            type_filter: If given, only include venues of this VenueType.

        Returns:
            `{unit_id, venue_type, total_count, page, per_page, total_pages,
            venues}`, where each venue is `{id, name, type, coordinates,
            properties, geo_unit, subsets, child_count,
            total_child_members}`. Empty result if `unit_id` is unknown.
        """
        unit = self._geography.get_unit_by_id(unit_id)
        if unit is None or self._subtree_index is None:
            return {'unit_id': unit_id, 'venue_type': type_filter, 'total_count': 0,
                    'page': page, 'per_page': per_page, 'total_pages': 0, 'venues': []}

        rows = np.sort(self._subtree_index.venue_rows(unit.id))

        with h5py.File(self._hdf5_path, 'r') as f:
            type_names = self._venue_type_names_cache

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
            'unit_id': unit_id, 'venue_type': type_filter, 'total_count': total,
            'page': page, 'per_page': per_page,
            'total_pages': calc_total_pages(total, per_page), 'venues': venues,
        }

    def load_venues_by_type(self, venue_type: str) -> list[dict]:
        """All venues of `venue_type` with coordinates, as map-ready rows.

        Bulk array read — no per-venue Python objects. Used by WorldMap to
        seed map markers.

        Args:
            venue_type: VenueType name to filter by.

        Returns:
            A list of `{id, name, type, geo_unit, coordinates, num_members,
            properties}` dicts. Venues without coordinates are skipped.
            Empty list if `venue_type` is unknown.
        """
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

    def get_venue_geo_unit_and_type(self, venue_id: int) -> tuple[int, str] | None:
        """Return (geo_unit_id, venue_type_name) for a venue, or None if unknown."""
        row = int(self._venue_id_to_idx[venue_id])
        if row == IdIndex.MISSING:
            return None
        with h5py.File(self._hdf5_path, 'r') as f:
            type_names = self._venue_type_names_cache
            type_code  = int(f['venues/types'][row])
            geo_id     = int(f['venues/geo_unit_ids'][row])
        venue_type = type_names[type_code] if type_code < len(type_names) else 'unknown'
        return (geo_id, venue_type)

    def load_venue_detail(self, venue_id: int) -> dict | None:
        """Full detail for one Venue, plus its Subsets (member counts only).

        Args:
            venue_id: Logical venue ID.

        Returns:
            `{id, name, type, geo_unit, coordinates, properties, subsets}`.
            None if `venue_id` is unknown.
        """
        row = int(self._venue_id_to_idx[venue_id])
        if row == IdIndex.MISSING:
            return None
        with h5py.File(self._hdf5_path, 'r') as f:
            type_names = self._venue_type_names_cache
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
        """Paginated ChildVenues for a ParentVenue.

        Args:
            venue_id: Logical ID of the ParentVenue.
            page: 1-indexed page number.
            per_page: Page size.

        Returns:
            `{parent_id, total_count, page, per_page, total_pages, venues}`,
            where each venue is shaped like `load_unit_venues`'s entries
            (with `child_count`/`total_child_members` fixed at 0, since
            ChildVenues never have their own children). Empty result if
            `venue_id` is unknown or has no children.
        """
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
                type_names = self._venue_type_names_cache
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

    # ── locate (page lookup via startup position arrays; geo_id read lazily) ─────
    #
    # `position`/`venue_type` come from O(1) resident-array reads (built at
    # launch); `geo_id` is fetched lazily, per record, straight from HDF5 —
    # the same pattern load_person_slim/load_unit_people use.

    def locate_venue(self, venue_id: int, per_page: int) -> dict | None:
        """Find which GeoUnit and page a venue appears on in its unit's listing.

        ChildVenues never appear in a unit's top-level venue list (only
        reachable by expanding their ParentVenue) — for those, geo_unit/
        venue_type/page describe the **parent's** reachable section, plus
        parent_venue_id/child_page locate the target within the parent's
        expanded children list.

        Args:
            venue_id: Logical venue ID.
            per_page: Page size of the target listing.

        Returns:
            `{geo_unit_id, venue_type, page}` (1-indexed page), plus
            `parent_venue_id`/`child_page` if `venue_id` is a ChildVenue.
            None if `venue_id` is unknown.
        """
        if self._venue_id_to_idx is None:
            return None
        row = int(self._venue_id_to_idx[venue_id])
        if row == IdIndex.MISSING:
            return None

        result_row    = row
        parent_extra  = {}
        if self._venue_parent_ids is not None and self._venue_parent_ids[row] != -1:
            parent_row = int(self._venue_parent_ids[row])
            result_row = parent_row
            child_position = (int(self._venue_child_position[row])
                              if self._venue_child_position is not None else 0)
            parent_extra = {
                'parent_venue_id': int(self._venue_ids[parent_row]),
                'child_page':      child_position // per_page + 1,
            }

        with h5py.File(self._hdf5_path, 'r') as f:
            geo_id = int(f['venues/geo_unit_ids'][result_row])
        unit       = self._geography.units_by_id.get(geo_id)
        type_code  = int(self._venue_types_arr[result_row])
        venue_type = (self._venue_type_names_cache[type_code]
                      if type_code < len(self._venue_type_names_cache) else 'unknown')
        position   = int(self._venue_list_position[result_row])
        return {
            'geo_unit_id': unit.id if unit else None,
            'venue_type':  venue_type,
            'page':        position // per_page + 1,
            **parent_extra,
        }

    # ── small helpers ────────────────────────────────────────────────────────────

    def _venue_subsets(self, f, venue_id: int) -> list[dict]:
        """`[{name, num_members}]` for a venue, from the sorted subset_venue_ids index.

        Args:
            f: Open HDF5 world file.
            venue_id: HDF5 row index of the venue (not the logical venue ID).
        """
        first = int(np.searchsorted(self._subset_venue_ids, venue_id, side='left'))
        last  = int(np.searchsorted(self._subset_venue_ids, venue_id, side='right'))
        if first >= last:
            return []
        names   = f['metadata/names/subsets'][first:last]
        counts  = f['venues/subsets/member_counts'][first:last]
        decoded_names = pd.Series(names).str.decode('utf-8')
        return [{'name': name, 'num_members': int(c)}
                for name, c in zip(decoded_names, counts)]

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

"""Person-domain reads for RecordReader."""

import h5py
import numpy as np
import pandas as pd

from world_reader.convert import SEX_DECODE, decode_str
from world_reader.id_index import IdIndex
from world_reader.pagination import calc_total_pages


class _PersonReads:
    """Mixin: assumes attributes set by RecordReader.__init__ (core.py)."""

    def load_person_activities(self, person_id: int) -> list[dict] | None:
        """Load the full ActivityMap for one person.

        Args:
            person_id: Logical person ID.

        Returns:
            A list of `{activity_name, venue_id, venue_name, venue_type,
            venue_geo_unit, subset_name}` dicts, one per activity. None if
            `person_id` is unknown.
        """
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

            act_data      = f['activity_mappings/activity_map/activity_data'][start:end]
            venue_names   = f['metadata/names/venues']
            subset_names  = f['metadata/names/subsets']
            venue_geo_ids = f['venues/geo_unit_ids']

            act_type_idx = act_data[:, 1]
            venue_row    = act_data[:, 2]
            subset_pos   = act_data[:, 3]

            # venue_type: WorldStore already holds this resident (built at
            # cold start) — a plain in-memory numpy gather, no HDF5 read and
            # no ordering constraint (h5py's fancy-index ordering rule below
            # only applies to on-disk reads, not numpy array indexing).
            venue_type_idx = self._venue_types_arr[venue_row]

            # venue_name / venue_geo_id: dedup before reading. h5py's
            # fancy-indexed reads require increasing, de-duplicated index
            # order (see load_venue_members's argsort/unsort workaround for
            # the same constraint) — np.unique's sorted+unique output
            # satisfies that for free, and as a bonus collapses repeat
            # visits to the same venue (e.g. "home" appearing many times in
            # one person's activities) to a single HDF5 read instead of one
            # read per activity.
            unique_venues, venue_inverse = np.unique(venue_row, return_inverse=True)
            venue_idx      = unique_venues.tolist()
            venue_name_u   = pd.Series(venue_names[venue_idx]).str.decode('utf-8').to_numpy()
            venue_geo_id_u = venue_geo_ids[venue_idx]
            venue_name    = venue_name_u[venue_inverse]
            venue_geo_id  = venue_geo_id_u[venue_inverse]

            # subset_name: a *second*, separate dedup stage chained off the
            # venue dedup above — not the same single-pass mechanism as
            # venue_name/venue_geo_id, because a subset_row can only be
            # computed once each unique venue's own first_sub/last_sub block
            # is known. So: resolve first_sub/last_sub per unique venue
            # in-memory (self._subset_venue_ids is already resident), scatter
            # back to every activity to get subset_row, then dedup *that*
            # before the one HDF5 read.
            first_sub_u = np.searchsorted(self._subset_venue_ids, unique_venues, side='left')
            last_sub_u  = np.searchsorted(self._subset_venue_ids, unique_venues, side='right')
            first_sub   = first_sub_u[venue_inverse]
            has_subset  = first_sub < last_sub_u[venue_inverse]

            subset_row = np.where(has_subset, first_sub + subset_pos, -1)
            valid      = subset_row >= 0
            unique_subset_rows, subset_inverse = np.unique(subset_row[valid], return_inverse=True)
            subset_name_u = pd.Series(
                subset_names[unique_subset_rows.tolist()]).str.decode('utf-8').to_numpy()

            subset_name = np.empty(len(act_data), dtype=object)
            subset_name[valid]  = subset_name_u[subset_inverse]
            subset_name[~valid] = [str(p) for p in subset_pos[~valid]]  # no-subset fallback

            act_name = [self._activity_names_cache[idx] for idx in act_type_idx]
            venue_id = self._venue_ids[venue_row]
            venue_type = [self._venue_type_names_cache[t]
                         if t < len(self._venue_type_names_cache) else 'unknown'
                         for t in venue_type_idx]
            venue_geo_unit = []
            for geo_id in venue_geo_id:
                unit = self._geography.units_by_id.get(int(geo_id))
                venue_geo_unit.append(unit.name if unit else str(int(geo_id)))

            # DataFrame index is 0..N-1 (act_data row order) throughout —
            # np.unique's return_inverse reconstructs original order by
            # construction, so to_dict('records') preserves activity order
            # exactly as stored, not sorted by venue.
            activities = pd.DataFrame({
                'activity_name':  act_name,
                'venue_id':       venue_id,
                'venue_name':     venue_name,
                'venue_type':     venue_type,
                'venue_geo_unit': venue_geo_unit,
                'subset_name':    subset_name,
            }).to_dict('records')

        return activities

    def load_person_slim(self, person_id: int) -> dict | None:
        """Load slim detail (no activities) for one person.

        Activities are loaded separately via `load_person_activities` —
        matching the slim-mode person panel, which lazily fetches activities
        on demand.

        Args:
            person_id: Logical person ID.

        Returns:
            `{id, age, sex, properties, geographical_unit}`, where
            `geographical_unit` is `{id, name, level, coordinates}` (or None
            if the person's geo unit is unknown). None if `person_id` is
            unknown.
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
            'properties': properties, 'geographical_unit': geo_info,
        }

    def load_unit_people(self, unit_id: int, page: int, per_page: int) -> dict:
        """Paginated id/age/sex for a GeoUnit's whole subtree, via SubtreeIndex.

        Args:
            unit_id: GeoUnit ID whose subtree to list.
            page: 1-indexed page number.
            per_page: Page size.

        Returns:
            `{unit_id, total_count, page, per_page, total_pages, people}`,
            where each person is `{id, age, sex, activities: [],
            primary_activity: None}`. Empty result if `unit_id` is unknown.
        """
        unit = self._geography.get_unit_by_id(unit_id)
        if unit is None or self._subtree_index is None:
            return {'unit_id': unit_id, 'total_count': 0, 'page': page,
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
                })

        return {
            'unit_id': unit_id, 'total_count': total, 'page': page,
            'per_page': per_page, 'total_pages': calc_total_pages(total, per_page),
            'people': people,
        }

    def locate_person(self, person_id: int, per_page: int) -> dict | None:
        """Find which GeoUnit and page a person appears on in their unit's listing.

        Args:
            person_id: Logical person ID.
            per_page: Page size of the target listing.

        Returns:
            `{geo_unit_id, page}` (1-indexed page). None if `person_id` is
            unknown.
        """
        if self._person_id_to_idx is None:
            return None
        array_idx = int(self._person_id_to_idx[person_id])
        if array_idx == IdIndex.MISSING:
            return None
        with h5py.File(self._hdf5_path, 'r') as f:
            geo_id = int(f['population/geo_unit_ids'][array_idx])
        unit      = self._geography.units_by_id.get(geo_id)
        position  = int(self._person_list_position[array_idx])
        return {
            'geo_unit_id': unit.id if unit else None,
            'page':        position // per_page + 1,
        }

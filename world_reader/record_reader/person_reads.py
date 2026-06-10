"""Person-domain reads for RecordReader."""

import h5py
import numpy as np

from world_reader.convert import SEX_DECODE, decode_str
from world_reader.id_index import IdIndex
from world_reader.pagination import calc_total_pages


class _PersonReads:
    """Mixin: assumes attributes set by RecordReader.__init__ (core.py)."""

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
                venue_row    = int(row[2])
                subset_pos   = int(row[3])

                act_name   = decode_str(act_names[act_type_idx])
                venue_name = decode_str(venue_names[venue_row])
                vtype_idx  = int(venue_types[venue_row])
                venue_type = venue_type_names[vtype_idx] if vtype_idx < len(venue_type_names) else 'unknown'

                venue_geo_id  = int(venue_geo_ids[venue_row])
                venue_unit    = self._geography.units_by_id.get(venue_geo_id)
                venue_geo_unit = venue_unit.name if venue_unit else str(venue_geo_id)

                first_sub = int(np.searchsorted(self._subset_venue_ids, venue_row, side='left'))
                last_sub  = int(np.searchsorted(self._subset_venue_ids, venue_row, side='right'))
                if first_sub < last_sub:
                    subset_row  = first_sub + subset_pos
                    subset_name = decode_str(subset_names[subset_row])
                else:
                    subset_name = str(subset_pos)

                activities.append({
                    'activity_name':  act_name,
                    'venue_id':       int(self._venue_ids[venue_row]),
                    'venue_name':     venue_name,
                    'venue_type':     venue_type,
                    'venue_geo_unit': venue_geo_unit,
                    'subset_name':    subset_name,
                })

        return activities

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

    def load_unit_people(self, unit_id: int, page: int, per_page: int) -> dict:
        """Paginated id/age/sex for the unit's whole subtree, via SubtreeIndex."""
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
                    'activities': [], 'primary_activity': None,
                })

        return {
            'unit_id': unit_id, 'total_count': total, 'page': page,
            'per_page': per_page, 'total_pages': calc_total_pages(total, per_page),
            'people': people,
        }

    def locate_person(self, person_id: int, per_page: int) -> dict | None:
        """Return {geo_unit_id, page} for person_id, or None if invalid."""
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

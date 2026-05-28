"""On-demand HDF5 data access for WorldExplorer detail views."""

import h5py
import numpy as np

_SEX_DECODE = {0: 'male', 1: 'female', 2: 'unknown'}


class ExplorerLoader:
    def __init__(self, hdf5_path, person_id_to_idx, subset_venue_ids, geography):
        self._hdf5_path = str(hdf5_path)
        self._person_id_to_idx = person_id_to_idx
        self._subset_venue_ids = subset_venue_ids
        self._geography = geography

    def load_person_activities(self, person_id: int) -> list[dict] | None:
        """Return ActivityMap records for person_id, or None if not found."""
        if (self._person_id_to_idx is None
                or person_id < 0
                or person_id >= len(self._person_id_to_idx)):
            return None

        person_array_idx = int(self._person_id_to_idx[person_id])

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
            venue_type_names = [self._decode(n) for n in f['metadata/registries/venue_types'][:]]
            venue_geo_ids    = f['venues/geo_unit_ids']

            activities = []
            for row in act_data:
                act_type_idx = int(row[1])
                venue_id     = int(row[2])
                subset_pos   = int(row[3])

                act_name   = self._decode(act_names[act_type_idx])
                venue_name = self._decode(venue_names[venue_id])
                vtype_idx  = int(venue_types[venue_id])
                venue_type = venue_type_names[vtype_idx] if vtype_idx < len(venue_type_names) else 'unknown'

                venue_geo_id  = int(venue_geo_ids[venue_id])
                venue_unit    = self._geography.units_by_id.get(venue_geo_id)
                venue_geo_unit = venue_unit.name if venue_unit else str(venue_geo_id)

                first_sub = int(np.searchsorted(self._subset_venue_ids, venue_id, side='left'))
                last_sub  = int(np.searchsorted(self._subset_venue_ids, venue_id, side='right'))
                if first_sub < last_sub:
                    subset_row  = first_sub + subset_pos
                    subset_name = self._decode(subset_names[subset_row])
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
        """Return paginated Subset member lists for a Venue."""
        first_sub = int(np.searchsorted(self._subset_venue_ids, venue_id, side='left'))
        last_sub  = int(np.searchsorted(self._subset_venue_ids, venue_id, side='right'))

        if first_sub >= last_sub:
            return {'venue_id': venue_id, 'venue_name': str(venue_id), 'subsets': []}

        with h5py.File(self._hdf5_path, 'r') as f:
            venue_name       = self._decode(f['metadata/names/venues'][venue_id])
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
                sname = self._decode(subset_names_arr[subset_row])

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
                        'total_pages': max(1, (total + per_page - 1) // per_page),
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

        return {'venue_id': venue_id, 'venue_name': venue_name, 'subsets': result_subsets}

    @staticmethod
    def _decode(val) -> str:
        return val.decode() if isinstance(val, bytes) else str(val)

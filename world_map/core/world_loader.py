"""
Standalone HDF5 loader for world_state.h5. No may dependencies.
Always loads in slim mode (skips activity_map relationships).
Adapted from may/serialization/world_loader.py.
"""

import logging
import time

import h5py
import numpy as np

from .world_data import (
    WorldData, GeographyManager, GeoUnit,
    PopulationManager, Person,
    VenueManager, Venue, Subset,
)

logger = logging.getLogger("world_loader")


# ─── numpy value conversion ───────────────────────────────────────────────────

def _convert_numpy_value(value):
    if value is None:
        return None
    if isinstance(value, (np.integer, np.int64, np.int32)):
        return int(value)
    if isinstance(value, (np.floating, np.float64, np.float32)):
        return float(value)
    if isinstance(value, np.ndarray):
        return [_convert_numpy_value(v) for v in value]
    if isinstance(value, (np.str_, np.bytes_)):
        return str(value)
    if isinstance(value, bytes):
        return value.decode('utf-8')
    return value


# ─── Public entry point ───────────────────────────────────────────────────────

def load_world_from_hdf5(input_file):
    """Load WorldData from world_state.h5 (slim mode).

    Args:
        input_file: path to world_state.h5 (str or Path)

    Returns:
        WorldData with geography, population, and venues.
    """
    logger.info("=" * 60)
    logger.info("LOADING WORLD FROM HDF5 (slim mode)")
    logger.info("=" * 60)
    logger.info(f"Input file: {input_file}")

    with h5py.File(input_file, 'r') as f:
        logger.info(f"  Geography units: {f.attrs.get('num_geo_units', 0):,}")
        logger.info(f"  People:          {f.attrs.get('num_people', 0):,}")
        logger.info(f"  Venues:          {f.attrs.get('num_venues', 0):,}")

        # ── metadata ─────────────────────────────────────────────────────────
        geo_names        = None
        level_registry   = None
        venue_names      = None
        type_registry    = None
        subset_names_arr = None

        if 'metadata' in f:
            meta = f['metadata']
            if 'names' in meta:
                if 'geography' in meta['names']:
                    geo_names = meta['names']['geography'][:].astype(str)
                if 'venues' in meta['names']:
                    venue_names = meta['names']['venues'][:].astype(str)
                if 'subsets' in meta['names']:
                    subset_names_arr = meta['names']['subsets'][:].astype(str)
            if 'registries' in meta:
                if 'geo_levels' in meta['registries']:
                    level_registry = meta['registries']['geo_levels'][:].astype(str)
                if 'venue_types' in meta['registries']:
                    type_registry = meta['registries']['venue_types'][:].astype(str)

        # ── geography ────────────────────────────────────────────────────────
        if 'geography' not in f:
            raise OSError("No geography data found in HDF5 file")
        logger.info("Loading geography...")
        geography = _load_geography(f['geography'], geo_names, level_registry)

        # ── population ───────────────────────────────────────────────────────
        t0 = time.perf_counter()
        population = None
        if 'population' in f:
            logger.info("Loading population...")
            try:
                population = _load_population(f['population'], geography)
            except Exception as exc:
                logger.warning(f"Failed to load population: {exc}")
        else:
            logger.warning("No population data in HDF5")
        logger.info(f"Population loaded in {time.perf_counter() - t0:.2f}s")

        # ── venues ───────────────────────────────────────────────────────────
        venue_manager = None
        if 'venues' in f:
            logger.info("Loading venues...")
            try:
                venue_manager = _load_venues(
                    f['venues'], geography,
                    venue_names, type_registry, subset_names_arr,
                )
            except Exception as exc:
                logger.warning(f"Failed to load venues: {exc}")
        else:
            logger.warning("No venue data in HDF5")

        # ── slim statistics ──────────────────────────────────────────────────
        slim_statistics = None
        logger.info("Computing slim statistics...")
        try:
            slim_statistics = _compute_slim_statistics(f)
        except Exception as exc:
            logger.warning(f"Failed to compute slim statistics: {exc}")

        unit_statistics = None
        if geography:
            logger.info("Computing per-unit statistics...")
            try:
                unit_statistics = _compute_unit_statistics(f, geography)
                logger.info(f"Per-unit statistics computed for {len(unit_statistics)} units.")
            except Exception as exc:
                logger.warning(f"Failed to compute unit statistics: {exc}")

    world = WorldData(geography=geography, population=population, venues=venue_manager)
    if slim_statistics is not None:
        world._slim_statistics = slim_statistics
    if unit_statistics is not None:
        world._unit_statistics = unit_statistics

    logger.info(f"Load complete: {world}")
    return world


# ─── Slim statistics (verbatim from may/serialization/world_loader.py) ────────

def _compute_array_stats(data, max_categories: int = 25) -> dict:
    """Return numeric or categorical summary stats for a single HDF5 dataset array."""
    if data.dtype.kind in ('f', 'u', 'i'):
        arr = data.astype(np.float64).ravel()
        finite = arr[np.isfinite(arr)]
        if len(finite) == 0:
            return {'type': 'numeric', 'count': 0}
        return {
            'type': 'numeric',
            'count': int(len(finite)),
            'mean': round(float(np.mean(finite)), 4),
            'std': round(float(np.std(finite)), 4),
            'min': float(np.min(finite)),
            'max': float(np.max(finite)),
            'p25': float(np.percentile(finite, 25)),
            'median': float(np.median(finite)),
            'p75': float(np.percentile(finite, 75)),
        }
    try:
        values = data.astype(str)
        unique, counts = np.unique(values, return_counts=True)
        total = int(len(values))
        order = np.argsort(-counts)
        top_u = unique[order[:max_categories]]
        top_c = counts[order[:max_categories]]
        return {
            'type': 'categorical',
            'count': total,
            'unique_count': int(len(unique)),
            'top_values': {
                str(k): {'count': int(v), 'pct': round(100.0 * v / total, 2)}
                for k, v in zip(top_u, top_c)
            },
        }
    except Exception as exc:
        return {'type': 'unknown', 'error': str(exc)}


def _compute_slim_statistics(f) -> dict:
    """Compute aggregate statistics from an open HDF5 file."""
    stats: dict = {}

    # ── person properties ────────────────────────────────────────────────────
    person_stats: dict = {}
    if 'population' in f:
        pop = f['population']
        if 'ages' in pop:
            person_stats['age'] = _compute_array_stats(pop['ages'][:])
        if 'sexes' in pop:
            sex_raw = pop['sexes'][:]
            if sex_raw.dtype.kind in ('u', 'i'):
                _labels = np.array(['male', 'female', 'unknown'])
                sexes = _labels[np.clip(sex_raw.astype(np.int64), 0, 2)]
            else:
                sexes = sex_raw.astype(str)
            person_stats['sex'] = _compute_array_stats(sexes)
        if 'properties' in pop:
            for prop_name in pop['properties'].keys():
                try:
                    person_stats[prop_name] = _compute_array_stats(
                        pop['properties'][prop_name][:]
                    )
                except Exception as exc:
                    person_stats[prop_name] = {'type': 'error', 'error': str(exc)}
    stats['person_properties'] = person_stats

    # ── subset sizes ─────────────────────────────────────────────────────────
    if 'venues' in f and 'subsets' in f['venues']:
        mc = f['venues']['subsets']['member_counts'][:].astype(np.int64)
        non_empty = mc[mc > 0]
        if len(non_empty):
            stats['subset_sizes'] = {
                'mean': round(float(np.mean(non_empty)), 2),
                'median': float(np.median(non_empty)),
                'min': int(np.min(non_empty)),
                'max': int(np.max(non_empty)),
                'total_subsets': int(len(mc)),
                'non_empty_subsets': int(len(non_empty)),
            }

    # ── activity map ─────────────────────────────────────────────────────────
    activity_group_name = (
        'activity_mappings' if 'activity_mappings' in f else 'relationships'
    )
    if activity_group_name in f and 'activity_map' in f[activity_group_name]:
        am               = f[activity_group_name]['activity_map']
        activity_names   = am['activity_names'][:].astype(str)
        activity_offsets = am['activity_offsets'][:]
        activity_data    = am['activity_data'][:]

        n_people = len(activity_offsets)
        n_rows   = len(activity_data)

        if n_rows > 0:
            pairs = np.unique(activity_data[:, [0, 1]].astype(np.int64), axis=0)
            people_per_act = np.zeros(len(activity_names), dtype=np.int64)
            np.add.at(people_per_act, pairs[:, 1], 1)
            unique_people    = int(len(np.unique(pairs[:, 0])))
            mean_unique_acts = len(pairs) / unique_people if unique_people else 0.0
        else:
            people_per_act   = np.zeros(len(activity_names), dtype=np.int64)
            unique_people    = 0
            mean_unique_acts = 0.0

        mean_assignments = n_rows / n_people if n_people else 0.0

        if 'venues' in f and 'subsets' in f['venues'] and n_rows > 0:
            mc_arr       = f['venues']['subsets']['member_counts'][:].astype(np.float64)
            non_empty_mc = mc_arr[mc_arr > 0]
            mean_contacts_est = (
                round(float(np.mean(non_empty_mc - 1)) * mean_assignments, 1)
                if len(non_empty_mc) else 0.0
            )
        else:
            mean_contacts_est = 0.0

        stats['activity_map'] = {
            'activity_counts': {
                str(activity_names[i]): int(people_per_act[i])
                for i in range(len(activity_names))
            },
            'total_people_with_activities': unique_people,
            'mean_activity_types_per_person': round(float(mean_unique_acts), 2),
            'mean_venue_assignments_per_person': round(float(mean_assignments), 2),
            'mean_contacts_estimate': mean_contacts_est,
        }

    # ── venue properties ─────────────────────────────────────────────────────
    venue_prop_stats: dict = {}
    if 'venues' in f and 'properties' in f['venues']:
        for venue_type in f['venues']['properties'].keys():
            vt_stats: dict = {}
            for prop_name in f['venues']['properties'][venue_type].keys():
                try:
                    vt_stats[prop_name] = _compute_array_stats(
                        f['venues']['properties'][venue_type][prop_name][:]
                    )
                except Exception as exc:
                    vt_stats[prop_name] = {'type': 'error', 'error': str(exc)}
            if vt_stats:
                venue_prop_stats[venue_type] = vt_stats
    stats['venue_properties'] = venue_prop_stats

    return stats


def _compute_unit_statistics(f, geography) -> dict:
    """Pre-compute per-geographic-unit statistics from HDF5 arrays."""
    if 'population' not in f:
        return {}

    pop             = f['population']
    person_ids_arr  = pop['ids'][:]
    person_geo_ids  = pop['geo_unit_ids'][:]
    ages            = pop['ages'][:].astype(np.float64)

    sex_raw = pop['sexes'][:]
    if sex_raw.dtype.kind in ('u', 'i'):
        _sex_labels = np.array(['male', 'female', 'unknown'])
        sexes = _sex_labels[np.clip(sex_raw.astype(np.int64), 0, 2)]
    else:
        sexes = sex_raw.astype(str)

    uid_to_name = {uid: u.name for uid, u in geography.units_by_id.items()}

    AGE_LABELS = ['0-15', '16-24', '25-34', '35-49', '50-64', '65+']
    AGE_BREAKS = [0, 16, 25, 35, 50, 65, np.inf]

    if len(person_geo_ids) == 0:
        return {}

    sort_idx = np.argsort(person_geo_ids, kind='stable')
    sg = person_geo_ids[sort_idx]
    sa = ages[sort_idx]
    ss = sexes[sort_idx]

    bounds   = np.where(np.diff(sg) != 0)[0] + 1
    g_starts = np.concatenate([[0], bounds])
    g_ends   = np.concatenate([bounds, [len(sg)]])

    leaf_stats: dict = {}
    for i, geo_id in enumerate(sg[g_starts]):
        unit_name = uid_to_name.get(int(geo_id))
        if unit_name is None:
            continue
        s, e = int(g_starts[i]), int(g_ends[i])

        age_dist: dict = {}
        for j, label in enumerate(AGE_LABELS):
            lo, hi = AGE_BREAKS[j], AGE_BREAKS[j + 1]
            age_dist[label] = int(np.sum((sa[s:e] >= lo) & (sa[s:e] < hi)))

        sex_u, sex_c = np.unique(ss[s:e], return_counts=True)
        leaf_stats[unit_name] = {
            'population':       int(e - s),
            'age_distribution': age_dist,
            'sex_distribution': {str(k): int(v) for k, v in zip(sex_u, sex_c)},
            'venue_types':      {},
            'activity_counts':  {},
        }

    # ── venue type counts per leaf unit ──────────────────────────────────────
    if 'venues' in f:
        v           = f['venues']
        v_geo_ids   = v['geo_unit_ids'][:]
        types_raw   = v['types'][:] if 'types' in v else np.array([], dtype='u1')

        type_reg = None
        try:
            type_reg = f['metadata']['registries']['venue_types'][:].astype(str)
        except Exception:
            pass

        if type_reg is not None and types_raw.dtype.kind in ('u', 'i') and len(types_raw):
            v_types = type_reg[types_raw.astype(int)]
        elif len(types_raw):
            v_types = types_raw.astype(str)
        else:
            v_types = np.array([])

        if len(v_types):
            v_sort    = np.argsort(v_geo_ids, kind='stable')
            svg       = v_geo_ids[v_sort]
            svt       = v_types[v_sort]
            vb        = np.where(np.diff(svg) != 0)[0] + 1
            vs_starts = np.concatenate([[0], vb])
            vs_ends   = np.concatenate([vb, [len(svg)]])

            for i, geo_id in enumerate(svg[vs_starts]):
                unit_name = uid_to_name.get(int(geo_id))
                if unit_name and unit_name in leaf_stats:
                    s, e = int(vs_starts[i]), int(vs_ends[i])
                    t_u, t_c = np.unique(svt[s:e], return_counts=True)
                    leaf_stats[unit_name]['venue_types'] = {
                        str(k): int(cnt) for k, cnt in zip(t_u, t_c)
                    }

    # ── activity counts per leaf unit ────────────────────────────────────────
    act_grp = 'activity_mappings' if 'activity_mappings' in f else 'relationships'
    if act_grp in f and 'activity_map' in f[act_grp]:
        am             = f[act_grp]['activity_map']
        activity_names = am['activity_names'][:].astype(str)
        act_data       = am['activity_data'][:]

        max_pid    = int(np.max(person_ids_arr))
        pid_to_geo = np.full(max_pid + 1, -1, dtype=np.int64)
        pid_to_geo[person_ids_arr.astype(np.int64)] = person_geo_ids.astype(np.int64)

        pa_pairs = np.unique(act_data[:, [0, 1]].astype(np.int64), axis=0)
        pa_pids  = pa_pairs[:, 0]
        valid    = pa_pids <= max_pid
        pa_pids, pa_acts = pa_pids[valid], pa_pairs[valid, 1]
        geo_ids  = pid_to_geo[pa_pids]
        valid2   = geo_ids >= 0

        geo_act = np.column_stack([geo_ids[valid2], pa_acts[valid2]])
        if len(geo_act):
            ga_sort   = np.lexsort((geo_act[:, 1], geo_act[:, 0]))
            gas       = geo_act[ga_sort]
            ga_b      = np.where(np.any(np.diff(gas, axis=0) != 0, axis=1))[0] + 1
            ga_starts = np.concatenate([[0], ga_b])
            ga_ends   = np.concatenate([ga_b, [len(gas)]])

            for k in range(len(ga_starts)):
                geo_id    = int(gas[ga_starts[k], 0])
                act_idx   = int(gas[ga_starts[k], 1])
                count     = int(ga_ends[k] - ga_starts[k])
                unit_name = uid_to_name.get(geo_id)
                if unit_name and unit_name in leaf_stats:
                    leaf_stats[unit_name]['activity_counts'][
                        str(activity_names[act_idx])
                    ] = count

    # ── aggregate upward through hierarchy ───────────────────────────────────
    all_stats = dict(leaf_stats)

    def _add(dst: dict, src: dict) -> None:
        dst['population'] = dst.get('population', 0) + src.get('population', 0)
        for label in AGE_LABELS:
            dst.setdefault('age_distribution', {})[label] = (
                dst.get('age_distribution', {}).get(label, 0)
                + src.get('age_distribution', {}).get(label, 0)
            )
        for sex, cnt in src.get('sex_distribution', {}).items():
            dst.setdefault('sex_distribution', {})[sex] = (
                dst.get('sex_distribution', {}).get(sex, 0) + cnt
            )
        for vt, cnt in src.get('venue_types', {}).items():
            dst.setdefault('venue_types', {})[vt] = (
                dst.get('venue_types', {}).get(vt, 0) + cnt
            )
        for act, cnt in src.get('activity_counts', {}).items():
            dst.setdefault('activity_counts', {})[act] = (
                dst.get('activity_counts', {}).get(act, 0) + cnt
            )

    def _aggregate(unit) -> dict:
        if not unit.children:
            return all_stats.get(unit.name, {
                'population': 0,
                'age_distribution': {k: 0 for k in AGE_LABELS},
                'sex_distribution': {},
                'venue_types': {},
                'activity_counts': {},
            })
        agg: dict = {
            'population': 0,
            'age_distribution': {k: 0 for k in AGE_LABELS},
            'sex_distribution': {},
            'venue_types': {},
            'activity_counts': {},
        }
        if unit.name in leaf_stats:
            _add(agg, leaf_stats[unit.name])
        for child in unit.children:
            _add(agg, _aggregate(child))
        all_stats[unit.name] = agg
        return agg

    for unit in geography.units_by_id.values():
        if unit.parent is None:
            _aggregate(unit)

    return all_stats


# ─── HDF5 loading functions ───────────────────────────────────────────────────

def _load_geography(geo_group, geo_names=None, level_registry=None):
    """Reconstruct GeographyManager from HDF5 geography group."""
    ids = geo_group['ids'][:]

    names = geo_names if geo_names is not None else geo_group['names'][:].astype(str)

    if level_registry is not None:
        levels = np.array([level_registry[int(v)] for v in geo_group['levels'][:]])
    else:
        levels = geo_group['levels'][:].astype(str)

    unique_levels = list(dict.fromkeys(str(lvl) for lvl in levels))
    parent_ids    = geo_group['parent_ids'][:]

    latitudes  = None
    longitudes = None
    if 'latitudes' in geo_group and 'longitudes' in geo_group:
        latitudes  = geo_group['latitudes'][:]
        longitudes = geo_group['longitudes'][:]

    properties_by_unit = {}
    if 'properties' in geo_group:
        for prop_name in geo_group['properties'].keys():
            properties_by_unit[prop_name] = geo_group['properties'][prop_name][:]

    geography = GeographyManager(levels=unique_levels)

    units_by_id = {}
    for i, (unit_id, name, level) in enumerate(zip(ids, names, levels)):
        coordinates = None
        if latitudes is not None and not np.isnan(latitudes[i]):
            coordinates = (float(latitudes[i]), float(longitudes[i]))

        properties = {
            prop_name: _convert_numpy_value(prop_array[i])
            for prop_name, prop_array in properties_by_unit.items()
        }

        unit = GeoUnit(
            unit_id=int(unit_id),
            name=str(name),
            level=str(level),
            coordinates=coordinates,
            properties=properties,
        )
        units_by_id[int(unit_id)] = unit

    for unit_id, parent_id in zip(ids, parent_ids):
        if int(parent_id) != -1:
            child  = units_by_id[int(unit_id)]
            parent = units_by_id[int(parent_id)]
            child.parent = parent
            parent.children.append(child)

    for unit in units_by_id.values():
        geography.add_unit(unit)

    logger.info(f"  Loaded {len(units_by_id)} geographical units")
    return geography


def _load_population(pop_group, geography):
    """Reconstruct PopulationManager from HDF5 population group (slim mode)."""
    ids          = pop_group['ids'][:]
    ages         = pop_group['ages'][:]
    geo_unit_ids = pop_group['geo_unit_ids'][:]

    _SEX_DECODE = {0: "male", 1: "female", 2: "unknown"}
    sex_raw = pop_group['sexes'][:]
    if sex_raw.dtype.kind in ('u', 'i'):
        sexes = np.array([_SEX_DECODE.get(int(v), "unknown") for v in sex_raw])
    else:
        sexes = sex_raw.astype(str)

    population        = PopulationManager()
    all_units         = geography.units_by_id
    num_people        = len(ids)
    progress_interval = max(1, num_people // 10)

    for i, (person_id, age, sex, geo_unit_id) in enumerate(
        zip(ids, ages, sexes, geo_unit_ids)
    ):
        geo_unit = all_units.get(int(geo_unit_id))
        person   = Person(
            person_id=int(person_id),
            age=int(age),
            sex=str(sex),
            geographical_unit=geo_unit,
        )
        population.add_person(person)
        if geo_unit is not None:
            geo_unit.people.append(person)

        if (i + 1) % progress_interval == 0 or (i + 1) == num_people:
            logger.info(f"    {i + 1:,}/{num_people:,} people ({100*(i+1)//num_people}%)")

    logger.info(f"  Loaded {num_people:,} people")
    return population


def _load_venues(venues_group, geography, venue_names=None,
                 type_registry=None, subset_names_arr=None):
    """Reconstruct VenueManager from HDF5 venues group (slim mode)."""
    ids          = venues_group['ids'][:]
    geo_unit_ids = venues_group['geo_unit_ids'][:]
    parent_ids   = venues_group['parent_ids'][:]

    names = venue_names if venue_names is not None else venues_group['names'][:].astype(str)

    if type_registry is not None:
        types = np.array([type_registry[int(v)] for v in venues_group['types'][:]])
    else:
        types = venues_group['types'][:].astype(str)

    latitudes  = None
    longitudes = None
    if 'latitudes' in venues_group and 'longitudes' in venues_group:
        latitudes  = venues_group['latitudes'][:]
        longitudes = venues_group['longitudes'][:]

    is_residence = None
    if 'is_residence' in venues_group:
        is_residence = venues_group['is_residence'][:]

    venue_manager       = VenueManager()
    all_units           = geography.units_by_id
    venues_by_global_id = {}
    num_venues          = len(ids)

    for i, (venue_id, name, venue_type, geo_unit_id) in enumerate(
        zip(ids, names, types, geo_unit_ids)
    ):
        geo_unit    = all_units.get(int(geo_unit_id))
        coordinates = None
        if latitudes is not None and not np.isnan(latitudes[i]):
            coordinates = (float(latitudes[i]), float(longitudes[i]))

        properties = {}
        if is_residence is not None:
            properties['is_residence'] = bool(is_residence[i])

        venue = Venue(
            venue_id=int(venue_id),
            name=str(name),
            venue_type=str(venue_type),
            geographical_unit=geo_unit,
            coordinates=coordinates,
            properties=properties,
        )
        venue_manager.add_venue(venue)
        venues_by_global_id[int(venue_id)] = venue
        if geo_unit is not None:
            geo_unit.venues.append(venue)

    # venue parent relationships (e.g. household → block)
    for venue_id, parent_id in zip(ids, parent_ids):
        child_vid  = int(venue_id)
        parent_vid = int(parent_id)
        if parent_vid != -1 and parent_vid in venues_by_global_id:
            venues_by_global_id[child_vid].parent = venues_by_global_id[parent_vid]

    logger.info(f"  Loaded {num_venues:,} venues")

    if 'subsets' in venues_group:
        _load_subsets(venues_group['subsets'], venues_by_global_id, subset_names_arr)

    return venue_manager


def _load_subsets(subsets_group, venues_by_global_id, subset_names_arr=None):
    """Attach Subset objects to venues (slim mode: member counts only)."""
    venue_ids     = subsets_group['venue_ids'][:]
    member_counts = subsets_group['member_counts'][:]

    if subset_names_arr is not None:
        subset_names = subset_names_arr
    else:
        subset_names = subsets_group['subset_names'][:].astype(str)

    num_subsets = len(venue_ids)
    for i, (venue_id, subset_name) in enumerate(zip(venue_ids, subset_names)):
        venue = venues_by_global_id.get(int(venue_id))
        if venue is None:
            continue
        subset = Subset(name=str(subset_name), num_members=int(member_counts[i]))
        venue.subsets[str(subset_name)] = subset

    logger.info(f"  Loaded {num_subsets:,} subsets")

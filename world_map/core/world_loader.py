"""
Standalone HDF5 loader for world_state.h5. No may dependencies.
Always loads in slim mode (skips activity_map relationships).
Adapted from may/serialization/world_loader.py.
"""

import logging
import time

import h5py
import numpy as np

from world_reader.convert import SEX_DECODE
from world_reader.geography import load_geography as _load_geography
from world_reader.statistics import compute_unit_statistics

from .world_data import (
    WorldData, PopulationManager, Person,
    VenueManager, Venue, Subset,
)

logger = logging.getLogger("world_loader")


# ─── Public entry point ───────────────────────────────────────────────────────

def load_world_from_hdf5(input_file, compute_activity_stats: bool = False):
    """Load WorldData from world_state.h5 (slim mode).

    Args:
        input_file: path to world_state.h5 (str or Path)
        compute_activity_stats: compute the per-unit and world-level activity
            breakdowns (the `np.unique` over the full activity map costs tens
            of seconds). Live WorldMap omits these from the landing page and
            unit-detail panel, so it loads with the fast default; the static
            export still shows activity stats, so it loads with `True`.

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
            slim_statistics = _compute_slim_statistics(f, compute_activity_stats)
        except Exception as exc:
            logger.warning(f"Failed to compute slim statistics: {exc}")

        unit_statistics = None
        if geography:
            logger.info("Computing per-unit statistics...")
            try:
                unit_statistics = compute_unit_statistics(
                    f, geography, include_activity_counts=compute_activity_stats
                )
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


def _compute_slim_statistics(f, compute_activity_stats: bool = False) -> dict:
    """Compute aggregate statistics from an open HDF5 file.

    `compute_activity_stats` gates the world-level activity-map breakdown
    (an `np.unique` over the full activity map costing tens of seconds) —
    skipped on the live WorldMap load path, computed for the static export.
    """
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
    if (
        compute_activity_stats
        and activity_group_name in f
        and 'activity_map' in f[activity_group_name]
    ):
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


# ─── HDF5 loading functions ───────────────────────────────────────────────────

def _load_population(pop_group, geography):
    """Reconstruct PopulationManager from HDF5 population group (slim mode)."""
    ids          = pop_group['ids'][:]
    ages         = pop_group['ages'][:]
    geo_unit_ids = pop_group['geo_unit_ids'][:]

    sex_raw = pop_group['sexes'][:]
    if sex_raw.dtype.kind in ('u', 'i'):
        sexes = np.array([SEX_DECODE.get(int(v), "unknown") for v in sex_raw])
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

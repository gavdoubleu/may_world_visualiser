"""Bespoke lazy loader for WorldExplorer.

Loads only what the explorer needs eagerly: the geography tree, aggregate
statistics, and lightweight per-unit row indices. Person/Venue/Subset records
are NOT materialised as Python objects — they are served on demand from HDF5 by
ExplorerLoader. Contrast with world_map's eager in-memory object model.

Reuses world_map's array-based helpers (_load_geography, _compute_slim_statistics,
_compute_unit_statistics); deliberately skips _load_population / _load_venues,
which build millions of objects and dominate cold-start (~9.5s for population
alone on the medieval dataset).
"""

import logging
import time

import h5py
import numpy as np

from world_map.core.world_loader import _load_geography
from world_map.core.world_data import AGE_LABELS, AGE_BREAKS, UnitStats

logger = logging.getLogger("explorer_world_loader")


class SubtreeIndex:
    """Maps each GeoUnit to the contiguous block of population / venue rows in its
    subtree (the unit plus all descendants).

    Built from a DFS pre-order interval over the geography tree: in pre-order a
    unit's subtree occupies a contiguous range of order values, so once the
    population (resp. venue) rows are sorted by their unit's pre-order value, the
    subtree's rows form a single contiguous slice — O(1) to locate, cheap to
    paginate.
    """

    def __init__(self, person_sorted_rows, person_ranges,
                 venue_sorted_rows, venue_ranges):
        self.person_sorted_rows = person_sorted_rows  # int64[num_people]: HDF5 row per slot
        self.person_ranges = person_ranges            # {unit_id: (start, end)}
        self.venue_sorted_rows = venue_sorted_rows     # int64[num_venues]
        self.venue_ranges = venue_ranges               # {unit_id: (start, end)}

    def person_rows(self, unit_id):
        """Population HDF5 row indices for the unit's subtree (arbitrary order)."""
        start, end = self.person_ranges.get(int(unit_id), (0, 0))
        return self.person_sorted_rows[start:end]

    def venue_rows(self, unit_id):
        """Venue HDF5 row indices for the unit's subtree (arbitrary order)."""
        start, end = self.venue_ranges.get(int(unit_id), (0, 0))
        return self.venue_sorted_rows[start:end]


class ExplorerWorld:
    """Lightweight world for the explorer: geography + stats + indices only.

    Duck-compatible with the subset of WorldData the explorer routes touch
    (`geography`, `_unit_statistics`, `_slim_statistics`). `population` / `venues`
    are intentionally absent — those are served lazily from HDF5.
    """

    def __init__(self, geography, slim_statistics, unit_statistics,
                 person_id_to_idx, subset_venue_ids, subtree_index):
        self.geography = geography
        self._slim_statistics = slim_statistics
        self._unit_statistics = unit_statistics
        self.person_id_to_idx = person_id_to_idx
        self.subset_venue_ids = subset_venue_ids
        self.subtree_index = subtree_index
        self.population = None
        self.venues = None

    def __str__(self):
        n_units = len(self.geography.units_by_id) if self.geography else 0
        return f"<ExplorerWorld: {n_units} units (lazy people/venues)>"


# ─── subtree index construction ───────────────────────────────────────────────

def _dfs_intervals(geography):
    """Assign each unit a DFS pre-order value and its subtree size.

    Returns (order_by_uid, size_by_uid). A unit's subtree covers pre-order values
    [order, order + size).
    """
    roots = [u for u in geography.units_by_id.values() if u.parent is None]

    order_by_uid: dict[int, int] = {}
    counter = 0
    stack = list(reversed(roots))
    while stack:
        unit = stack.pop()
        order_by_uid[unit.id] = counter
        counter += 1
        for child in reversed(unit.children):
            stack.append(child)

    size_by_uid: dict[int, int] = {}

    def _size(unit) -> int:
        total = 1
        for child in unit.children:
            total += _size(child)
        size_by_uid[unit.id] = total
        return total

    for root in roots:
        _size(root)

    return order_by_uid, size_by_uid


def _build_row_ranges(geo_ids, order_by_uid, size_by_uid, max_geo_id):
    """Sort HDF5 rows by their unit's pre-order value; return (sorted_rows, ranges).

    `sorted_rows[i]` is the HDF5 row index sitting at sorted slot i.
    `ranges[unit_id]` is the (start, end) slice of sorted_rows covering that
    unit's whole subtree. Rows whose geo id is not a known unit map to order -1
    and fall outside every subtree range.
    """
    geoid_to_order = np.full(max_geo_id + 1, -1, dtype=np.int64)
    for uid, order in order_by_uid.items():
        if 0 <= uid <= max_geo_id:
            geoid_to_order[uid] = order

    row_order    = geoid_to_order[geo_ids.astype(np.int64)]
    sort         = np.argsort(row_order, kind='stable')
    sorted_order = row_order[sort]
    sorted_rows  = sort.astype(np.int64)

    ranges: dict[int, tuple[int, int]] = {}
    for uid, order in order_by_uid.items():
        size  = size_by_uid[uid]
        start = int(np.searchsorted(sorted_order, order, side='left'))
        end   = int(np.searchsorted(sorted_order, order + size, side='left'))
        ranges[uid] = (start, end)

    return sorted_rows, ranges


def _build_subtree_index(f, geography):
    order_by_uid, size_by_uid = _dfs_intervals(geography)
    unit_ids_max = max(order_by_uid) if order_by_uid else 0

    person_geo_ids = f['population/geo_unit_ids'][:]
    venue_geo_ids  = f['venues/geo_unit_ids'][:]

    max_geo_id = max(
        unit_ids_max,
        int(person_geo_ids.max()) if len(person_geo_ids) else 0,
        int(venue_geo_ids.max())  if len(venue_geo_ids)  else 0,
    )

    person_rows, person_ranges = _build_row_ranges(
        person_geo_ids, order_by_uid, size_by_uid, max_geo_id)
    venue_rows, venue_ranges = _build_row_ranges(
        venue_geo_ids, order_by_uid, size_by_uid, max_geo_id)

    return SubtreeIndex(person_rows, person_ranges, venue_rows, venue_ranges)


# ─── per-unit statistics (explorer-slim: no activity-map crunch) ──────────────

def _compute_explorer_unit_statistics(f, geography):
    """Per-unit population / age / sex / venue-type counts, aggregated upward.

    Deliberately omits activity_counts: the explorer UI never displays them, and
    computing them means an np.unique over the ~30M-row activity map (~tens of
    seconds). world_map's _compute_unit_statistics keeps that block; the explorer
    does not need it.
    """
    if 'population' not in f:
        return {}

    pop            = f['population']
    person_geo_ids = pop['geo_unit_ids'][:]
    ages           = pop['ages'][:].astype(np.float64)

    sex_raw = pop['sexes'][:]
    if sex_raw.dtype.kind in ('u', 'i'):
        _sex_labels = np.array(['male', 'female', 'unknown'])
        sexes = _sex_labels[np.clip(sex_raw.astype(np.int64), 0, 2)]
    else:
        sexes = sex_raw.astype(str)

    uid_to_name   = {uid: u.name for uid, u in geography.units_by_id.items()}
    AGE_BREAKS_NP = AGE_BREAKS[:-1] + [np.inf]

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
            lo, hi = AGE_BREAKS_NP[j], AGE_BREAKS_NP[j + 1]
            age_dist[label] = int(np.sum((sa[s:e] >= lo) & (sa[s:e] < hi)))

        sex_u, sex_c = np.unique(ss[s:e], return_counts=True)
        leaf_stats[unit_name] = {
            'population':       int(e - s),
            'age_distribution': age_dist,
            'sex_distribution': {str(k): int(v) for k, v in zip(sex_u, sex_c)},
            'venue_types':      {},
        }

    # ── venue type counts per leaf unit ──────────────────────────────────────
    if 'venues' in f:
        v         = f['venues']
        v_geo_ids = v['geo_unit_ids'][:]
        types_raw = v['types'][:] if 'types' in v else np.array([], dtype='u1')

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

    def _aggregate(unit) -> dict:
        if not unit.children:
            return all_stats.get(unit.name, {
                'population': 0,
                'age_distribution': {k: 0 for k in AGE_LABELS},
                'sex_distribution': {},
                'venue_types': {},
            })
        agg: dict = {
            'population': 0,
            'age_distribution': {k: 0 for k in AGE_LABELS},
            'sex_distribution': {},
            'venue_types': {},
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

    return {
        name: UnitStats(
            population=int(d['population']),
            age_distribution={k: int(v) for k, v in d['age_distribution'].items()},
            sex_distribution={str(k): int(v) for k, v in d['sex_distribution'].items()},
            venue_types={str(k): int(v) for k, v in d.get('venue_types', {}).items()},
        )
        for name, d in all_stats.items()
    }


# ─── public entry point ───────────────────────────────────────────────────────

def load_explorer_world(input_file):
    """Load an ExplorerWorld from world_state.h5 without materialising people/venues."""
    logger.info("Loading explorer world (lazy mode) from %s", input_file)
    t_start = time.perf_counter()

    with h5py.File(input_file, 'r') as f:
        geo_names = level_registry = None
        if 'metadata' in f:
            meta = f['metadata']
            if 'names' in meta and 'geography' in meta['names']:
                geo_names = meta['names']['geography'][:].astype(str)
            if 'registries' in meta and 'geo_levels' in meta['registries']:
                level_registry = meta['registries']['geo_levels'][:].astype(str)

        if 'geography' not in f:
            raise OSError("No geography data found in HDF5 file")

        geography       = _load_geography(f['geography'], geo_names, level_registry)
        unit_statistics = _compute_explorer_unit_statistics(f, geography)

        # lookup arrays (cheap; serve single-record lazy reads)
        person_ids       = f['population/ids'][:]
        person_id_to_idx = np.empty_like(person_ids)
        person_id_to_idx[person_ids] = np.arange(len(person_ids), dtype=person_ids.dtype)
        subset_venue_ids = f['venues/subsets/venue_ids'][:]

        subtree_index = _build_subtree_index(f, geography)

    world = ExplorerWorld(
        geography, None, unit_statistics,
        person_id_to_idx, subset_venue_ids, subtree_index,
    )
    logger.info("Explorer world loaded in %.2fs: %s",
                time.perf_counter() - t_start, world)
    return world

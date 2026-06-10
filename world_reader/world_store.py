"""Lazy world store shared by WorldMap and WorldExplorer.

Holds only what both apps need resident: the geography tree, aggregate
statistics, the geographical distribution, and lightweight per-unit row
indices. Person/Venue/Subset records are NOT materialised as Python objects —
they are served on demand from HDF5 by RecordReader. Per-row geo_unit_ids are
likewise not kept resident; they are read lazily, per record, mirroring
load_person_slim.

Reuses world_reader's shared load_geography and compute_unit_statistics;
deliberately skips loading population / venues as Python objects, which would
build millions of objects and dominate cold-start (~9.5s for population alone
on the medieval dataset).
"""

import logging
import time
from pathlib import Path

import h5py
import numpy as np

from world_reader import compute_unit_statistics
from world_reader.geography import load_geography
from world_reader.id_index import IdIndex
from world_reader.statistics import compute_geographical_distribution, compute_slim_statistics

logger = logging.getLogger("world_store")


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


class WorldStore:
    """Lightweight resident world store: geography + stats + indices only.

    `population` / `venues` are intentionally absent (always None) — those
    are served lazily from HDF5 via `RecordReader`.

    Attributes:
        geography (GeographyManager): The GeoUnit hierarchy.
        geographical_distribution (dict): Per-level counts of people by
            their direct geo unit.
        person_id_to_idx (IdIndex): Logical person ID -> population row.
        venue_id_to_idx (IdIndex): Logical venue ID -> venues row.
        venue_ids: Logical venue ID per venues row, or None.
        subset_venue_ids: Sorted venues-row index per subset, for
            binary-search lookup of a venue's subsets.
        subtree_index (SubtreeIndex): O(1) subtree row-range lookups.
        venue_types_arr: Per-venue type code array.
        venue_type_names: Type names indexed by code.
        venue_list_position: Per-venue rank within its direct unit's
            top-level, type-filtered venue listing.
        person_list_position: Per-person rank within their direct unit's
            person listing.
        venue_parent_ids: Per-venue parent venue row, or -1 for top-level.
        venue_child_counts: Per-venue count of ChildVenues.
        venue_child_total_members: Per-venue summed member count of its
            ChildVenues.
        venue_child_position: Per-ChildVenue rank within its ParentVenue's
            children list.
        children_by_parent_sorted: ChildVenue rows sorted by parent row.
        children_parent_ids_sorted: Parent rows aligned with
            `children_by_parent_sorted`, for binary search.
        population: Always None — Person objects are not materialised.
        venues: Always None — Venue objects are not materialised.
    """

    def __init__(self, geography, slim_statistics, unit_statistics,
                 geographical_distribution,
                 person_id_to_idx, subset_venue_ids, subtree_index,
                 venue_types_arr,
                 venue_type_names, venue_list_position, person_list_position,
                 venue_parent_ids=None, venue_child_counts=None,
                 venue_child_total_members=None, venue_child_position=None,
                 children_by_parent_sorted=None, children_parent_ids_sorted=None,
                 venue_ids=None, venue_id_to_idx=None):
        self.geography = geography
        self._slim_statistics = slim_statistics
        self._unit_statistics = unit_statistics
        self.geographical_distribution = geographical_distribution
        self.person_id_to_idx = person_id_to_idx
        self.subset_venue_ids = subset_venue_ids
        self.venue_ids = venue_ids
        self.venue_id_to_idx = venue_id_to_idx
        self.subtree_index = subtree_index
        self.venue_types_arr      = venue_types_arr
        self.venue_type_names     = venue_type_names
        self.venue_list_position  = venue_list_position
        self.person_list_position = person_list_position
        self.venue_parent_ids             = venue_parent_ids
        self.venue_child_counts           = venue_child_counts
        self.venue_child_total_members    = venue_child_total_members
        self.venue_child_position         = venue_child_position
        self.children_by_parent_sorted    = children_by_parent_sorted
        self.children_parent_ids_sorted   = children_parent_ids_sorted
        self.population = None
        self.venues = None

    def __str__(self):
        n_units = len(self.geography.units_by_id) if self.geography else 0
        return f"<WorldStore: {n_units} units (lazy people/venues)>"


# ─── subtree index construction ───────────────────────────────────────────────

def _dfs_intervals(geography):
    """Assign each unit a DFS pre-order value and its subtree size.

    A unit's subtree covers pre-order values [order, order + size).

    Args:
        geography: GeographyManager with the GeoUnit hierarchy already loaded.

    Returns:
        `(order_by_uid, size_by_uid)`, both `{unit_id: int}`.
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
    """Sort HDF5 rows by their unit's pre-order value.

    Rows whose geo id is not a known unit map to order -1 and fall outside
    every subtree range.

    Args:
        geo_ids: int array, one geo-unit id per HDF5 row.
        order_by_uid: `{unit_id: pre-order value}`, from `_dfs_intervals`.
        size_by_uid: `{unit_id: subtree size}`, from `_dfs_intervals`.
        max_geo_id: Largest geo-unit id, for sizing the lookup array.

    Returns:
        `(sorted_rows, ranges)` where `sorted_rows[i]` is the HDF5 row index
        at sorted slot `i`, and `ranges[unit_id]` is the `(start, end)` slice
        of `sorted_rows` covering that unit's whole subtree.
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


def _build_subtree_index(f, geography) -> tuple[SubtreeIndex, np.ndarray, np.ndarray]:
    """Build the SubtreeIndex plus the raw geo-unit-id arrays it was built from.

    Args:
        f: Open HDF5 world file.
        geography: GeographyManager with the GeoUnit hierarchy already loaded.

    Returns:
        `(index, person_geo_ids, venue_geo_ids)` — the SubtreeIndex, and the
        raw `population/geo_unit_ids` / `venues/geo_unit_ids` arrays (reused
        by `_build_locate_indices`).
    """
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

    index = SubtreeIndex(person_rows, person_ranges, venue_rows, venue_ranges)
    return index, person_geo_ids, venue_geo_ids


# ─── locate index construction ───────────────────────────────────────────────

def _build_locate_indices(subtree_index, geography,
                          venue_geo_unit_ids, venue_types_arr,
                          person_geo_unit_ids, venue_parent_ids=None):
    """Build O(1) position lookup arrays for venue and person locate endpoints.

    Positions are 0-indexed and per_page-independent; callers divide by
    per_page to get page numbers.

    Args:
        subtree_index: SubtreeIndex from `_build_subtree_index`.
        geography: GeographyManager with the GeoUnit hierarchy already loaded.
        venue_geo_unit_ids: int array, one direct geo-unit id per venue.
        venue_types_arr: int array of per-venue type codes.
        person_geo_unit_ids: int array, one direct geo-unit id per person.
        venue_parent_ids: int array of per-venue parent rows (-1 for
            top-level), or None to treat every venue as top-level.

    Returns:
        `(venue_list_position, person_list_position)`. `venue_list_position
        [row]` is the rank of that venue within its direct geo unit's
        type-filtered, top-level-only subtree listing.
        `person_list_position[row]` is the rank of that person within their
        direct geo unit's subtree person listing.
    """
    num_venues  = len(venue_geo_unit_ids)
    num_persons = len(person_geo_unit_ids)

    venue_list_position  = np.zeros(num_venues,  dtype=np.int32)
    person_list_position = np.zeros(num_persons, dtype=np.int32)

    # mask identifying venues that are NOT children (these appear in the top-level list)
    if venue_parent_ids is not None and len(venue_parent_ids) == num_venues:
        is_top_level = venue_parent_ids == -1
    else:
        is_top_level = np.ones(num_venues, dtype=bool)

    for unit_id in geography.units_by_id:
        # ── venue positions ───────────────────────────────────────────────────
        v_rows = np.sort(subtree_index.venue_rows(unit_id))
        if len(v_rows):
            # exclude child venues from position ranking
            top_level_mask = is_top_level[v_rows]
            v_rows_top     = v_rows[top_level_mask]
            direct_mask    = venue_geo_unit_ids[v_rows_top] == unit_id
            if np.any(direct_mask):
                v_types = venue_types_arr[v_rows_top]
                for type_code in np.unique(v_types[direct_mask]):
                    same_type_mask   = (v_types == type_code)
                    same_type_rows   = v_rows_top[same_type_mask]
                    direct_of_type   = direct_mask & same_type_mask
                    direct_venue_ids = v_rows_top[direct_of_type]
                    positions        = np.searchsorted(same_type_rows, direct_venue_ids)
                    venue_list_position[direct_venue_ids] = positions

        # ── person positions ──────────────────────────────────────────────────
        p_rows = np.sort(subtree_index.person_rows(unit_id))
        if len(p_rows):
            direct_mask    = person_geo_unit_ids[p_rows] == unit_id
            direct_indices = np.where(direct_mask)[0]
            person_list_position[p_rows[direct_indices]] = direct_indices

    return venue_list_position, person_list_position


# ─── public entry point ───────────────────────────────────────────────────────

def build_world_store(input_file: str | Path, compute_activity_stats: bool = False) -> WorldStore:
    """Build a WorldStore from world_state.h5 without materialising people/venues.

    Args:
        input_file: path to world_state.h5 (str or Path)
        compute_activity_stats: compute the per-unit and world-level activity
            breakdowns (the `np.unique` over the full activity map costs tens
            of seconds). Live loads omit these (fast default); the static
            export needs them, so it loads with `True`.

    Returns:
        A populated WorldStore.

    Raises:
        OSError: If the HDF5 file has no `geography` group.
    """
    logger.info("Building world store (lazy mode) from %s", input_file)
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

        geography       = load_geography(f['geography'], geo_names, level_registry)
        unit_statistics = compute_unit_statistics(
            f, geography, include_activity_counts=compute_activity_stats
        )
        slim_statistics = compute_slim_statistics(f, compute_activity_stats)

        # lookup arrays (cheap; serve single-record lazy reads)
        person_ids       = f['population/ids'][:]
        person_id_to_idx = IdIndex(person_ids)
        subset_venue_ids = f['venues/subsets/venue_ids'][:]

        venue_ids        = f['venues/ids'][:] if 'venues/ids' in f else np.array([], dtype=np.int32)
        venue_id_to_idx  = IdIndex(venue_ids)

        subtree_index, person_geo_unit_ids, venue_geo_unit_ids = (
            _build_subtree_index(f, geography))

        geographical_distribution = compute_geographical_distribution(
            person_geo_unit_ids, geography)

        venue_types_arr  = f['venues/types'][:] if 'venues/types' in f else np.array([], dtype=np.uint8)
        venue_type_names = []
        if 'metadata/registries/venue_types' in f:
            venue_type_names = [n.decode() if isinstance(n, bytes) else str(n)
                                for n in f['metadata/registries/venue_types'][:]]

        num_venues = len(venue_types_arr)
        raw_parent_ids = (f['venues/parent_ids'][:]
                          if 'venues/parent_ids' in f
                          else np.full(num_venues, -1, dtype=np.int32))
        venue_parent_ids = raw_parent_ids.astype(np.int64)

        # child venue index (mirrors subset_venue_ids binary-search pattern)
        child_mask               = venue_parent_ids != -1
        child_venue_ids          = np.where(child_mask)[0].astype(np.int64)
        child_parent_ids         = venue_parent_ids[child_mask]
        sort_idx                 = np.argsort(child_parent_ids, kind='stable')
        children_by_parent_sorted  = child_venue_ids[sort_idx]
        children_parent_ids_sorted = child_parent_ids[sort_idx]

        venue_child_counts = np.zeros(num_venues, dtype=np.int32)
        if len(child_parent_ids):
            np.add.at(venue_child_counts, child_parent_ids, 1)

        # rank of each ChildVenue within its ParentVenue's children list
        # (same diff-grouping technique as _build_locate_indices: contiguous
        # runs in the parent-sorted array get 0..n-1 via np.arange)
        venue_child_position = np.zeros(num_venues, dtype=np.int32)
        if len(children_parent_ids_sorted):
            run_bounds  = np.where(np.diff(children_parent_ids_sorted) != 0)[0] + 1
            run_starts  = np.concatenate([[0], run_bounds])
            run_ends    = np.concatenate([run_bounds, [len(children_parent_ids_sorted)]])
            for start, end in zip(run_starts, run_ends):
                venue_child_position[children_by_parent_sorted[start:end]] = np.arange(end - start)

        # per-venue member total from subset member_counts
        venue_total_members = np.zeros(num_venues, dtype=np.int32)
        if 'venues/subsets/member_counts' in f and 'venues/subsets/venue_ids' in f:
            mc  = f['venues/subsets/member_counts'][:]
            svi = f['venues/subsets/venue_ids'][:]
            np.add.at(venue_total_members, svi, mc)

        venue_child_total_members = np.zeros(num_venues, dtype=np.int32)
        if len(child_venue_ids):
            np.add.at(venue_child_total_members, child_parent_ids,
                      venue_total_members[child_venue_ids])

    venue_list_position, person_list_position = _build_locate_indices(
        subtree_index, geography,
        venue_geo_unit_ids, venue_types_arr, person_geo_unit_ids,
        venue_parent_ids=venue_parent_ids,
    )

    world = WorldStore(
        geography, slim_statistics, unit_statistics,
        geographical_distribution,
        person_id_to_idx, subset_venue_ids, subtree_index,
        venue_types_arr,
        venue_type_names, venue_list_position, person_list_position,
        venue_parent_ids=venue_parent_ids,
        venue_child_counts=venue_child_counts,
        venue_child_total_members=venue_child_total_members,
        venue_child_position=venue_child_position,
        children_by_parent_sorted=children_by_parent_sorted,
        children_parent_ids_sorted=children_parent_ids_sorted,
        venue_ids=venue_ids,
        venue_id_to_idx=venue_id_to_idx,
    )
    logger.info("World store built in %.2fs: %s",
                time.perf_counter() - t_start, world)
    return world

"""HDF5 IO layer for simulation events. All h5py calls live here."""

import logging
from collections import defaultdict
from pathlib import Path
from typing import Optional

import h5py
import numpy as np

from world_map.events.event_bundle import EventDataBundle
from world_map.events.event_aggregator import EventAggregator

logger = logging.getLogger(__name__)

_MAX_ARRAY_ID = 50_000_000  # safety cap for dense lookup arrays (~200 MB for int32)


def load_event_bundle(events_path: Path | str) -> EventDataBundle:
    """
    Read HDF5, sort events, build dense lookup arrays.
    Discovers event types dynamically from the 'events/' group.
    """
    events_path = Path(events_path)

    if not events_path.exists():
        logger.warning(f"Events file not found: {events_path}")
        return EventDataBundle(
            events_sorted={}, events_times={},
            venue_geo_array=None, person_geo_array=None,
            n_geo=1, time_min=0.0, time_max=0.0,
        )

    logger.info(f"Loading events from {events_path}")

    with h5py.File(events_path, 'r') as f:
        events_sorted, events_times, time_min, time_max = _read_and_sort_events(f)
        venue_geo_array, person_geo_array, n_geo = _build_lookup_arrays(f)

    logger.info("  Events pre-sorted by time for fast window queries")
    return EventDataBundle(
        events_sorted=events_sorted,
        events_times=events_times,
        venue_geo_array=venue_geo_array,
        person_geo_array=person_geo_array,
        n_geo=n_geo,
        time_min=time_min,
        time_max=time_max,
    )


def load_event_aggregator(
    events_path: Path | str,
    geo_unit_coords: dict[int, tuple[float, float]],
    geo_unit_population: dict[int, int],
) -> EventAggregator:
    """Production factory: read HDF5, return ready EventAggregator."""
    bundle = load_event_bundle(events_path)
    return EventAggregator(bundle, geo_unit_coords, geo_unit_population)


def load_events_with_world(events_path: str, world=None) -> EventAggregator:
    """Production EventAggregator factory: pull geo coords + population from a
    resident WorldStore, read events HDF5, return a ready aggregator.

    Coords and population both come from already-resident state — coordinates
    from the geography tree, population from the subtree-aggregated
    `_unit_statistics` (the lazy backend never materialises `GeoUnit.people`,
    so the old `get_people()` count was always empty → rate always 0).
    """
    coords: dict[int, tuple[float, float]] = {}
    population: dict[int, int] = {}

    if world and world.geography:
        coords = world.geography.geo_unit_coords()
        unit_statistics = getattr(world, '_unit_statistics', None) or {}
        population = {
            unit.id: unit_statistics[unit.id].population
            for unit in world.geography.units_by_id.values()
            if unit.id in unit_statistics
        }

    aggregator = load_event_aggregator(events_path, coords, population)
    logger.info(f"Set {len(coords)} geo_unit coordinates from world")
    return aggregator


# ---------------------------------------------------------------------------
# Private IO helpers
# ---------------------------------------------------------------------------

def _read_and_sort_events(
    f: h5py.File,
) -> tuple[dict, dict, float, float]:
    """Discover event types from 'events/' group, load and sort each."""
    events_sorted: dict[str, np.ndarray] = {}
    events_times: dict[str, np.ndarray] = {}
    # Each sorted array is time-ascending, so its first/last element bound that
    # type — collect per-type endpoints rather than materialising every time.
    type_mins: list[float] = []
    type_maxes: list[float] = []

    if 'events' not in f:
        return events_sorted, events_times, 0.0, 0.0

    for event_type in f['events'].keys():
        data = f[f'events/{event_type}'][:]
        if len(data) == 0:
            events_sorted[event_type] = data
            events_times[event_type] = np.array([], dtype=np.float32)
            logger.info(f"  {event_type}: 0 records")
            continue

        sort_idx = np.argsort(data['time'], kind='stable')
        sorted_arr = data[sort_idx]
        sorted_times = sorted_arr['time']
        events_sorted[event_type] = sorted_arr
        events_times[event_type] = sorted_times.astype(np.float32)
        logger.info(f"  Loaded {len(data)} {event_type}")

        type_mins.append(float(sorted_times[0]))
        type_maxes.append(float(sorted_times[-1]))

    time_min = min(type_mins) if type_mins else 0.0
    time_max = max(type_maxes) if type_maxes else 0.0
    if type_mins:
        logger.info(f"  Time range: {time_min:.1f} - {time_max:.1f}")

    return events_sorted, events_times, time_min, time_max


def _read_lookup_columns(
    f: h5py.File, group: str, id_field: str,
) -> tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """Read an id→geo_unit lookup table as two int32 columns (no per-row loop)."""
    if group not in f:
        return None, None
    rows = f[group][:]
    ids   = rows[id_field].astype(np.int32)
    geos  = rows['geo_unit_id'].astype(np.int32)
    logger.info(f"  Loaded {len(ids)} {group} mappings")
    return ids, geos


def _scatter_dense(ids: Optional[np.ndarray], geos: Optional[np.ndarray],
                   label: str) -> Optional[np.ndarray]:
    """Scatter (id, geo) columns into a dense -1-filled int32 lookup array."""
    if ids is None or len(ids) == 0:
        return None
    max_id = int(ids.max())
    if max_id >= _MAX_ARRAY_ID:
        return None
    dense = np.full(max_id + 1, -1, dtype=np.int32)
    dense[ids] = geos
    logger.info(f"  Built {label} lookup array (size {max_id + 1:,})")
    return dense


def _build_lookup_arrays(
    f: h5py.File,
) -> tuple[Optional[np.ndarray], Optional[np.ndarray], int]:
    """Build dense int32 lookup arrays from HDF5 lookup tables.

    Vectorised column reads + scatter — no per-row Python loop over the
    (potentially multi-million-row) lookup tables.
    """
    venue_ids, venue_geos   = _read_lookup_columns(f, 'lookups/venues', 'venue_id')
    person_ids, person_geos = _read_lookup_columns(f, 'lookups/people', 'person_id')

    venue_geo_array  = _scatter_dense(venue_ids, venue_geos, 'venue')
    person_geo_array = _scatter_dense(person_ids, person_geos, 'person')

    geo_maxes = [int(geos.max()) for geos in (venue_geos, person_geos)
                 if geos is not None and len(geos)]
    n_geo = max(geo_maxes) + 1 if geo_maxes else 1

    return venue_geo_array, person_geo_array, n_geo

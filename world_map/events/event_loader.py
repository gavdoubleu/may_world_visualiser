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
    """Backward-compatible wrapper. Extracts geo data from world, returns EventAggregator."""
    coords: dict[int, tuple[float, float]] = {}
    population: dict[int, int] = {}

    if world and world.geography:
        for level in world.geography.levels:
            for unit in world.geography.get_units_by_level(level).values():
                if unit.coordinates:
                    coords[unit.id] = unit.coordinates
                if unit.people:
                    population[unit.id] = len(unit.get_people())

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
    all_times: list = []

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
        events_sorted[event_type] = sorted_arr
        events_times[event_type] = sorted_arr['time'].astype(np.float32)
        logger.info(f"  Loaded {len(data)} {event_type}")

        if 'time' in data.dtype.names:
            all_times.extend(data['time'])

    time_min = float(min(all_times)) if all_times else 0.0
    time_max = float(max(all_times)) if all_times else 0.0
    if all_times:
        logger.info(f"  Time range: {time_min:.1f} - {time_max:.1f}")

    return events_sorted, events_times, time_min, time_max


def _build_lookup_arrays(
    f: h5py.File,
) -> tuple[Optional[np.ndarray], Optional[np.ndarray], int]:
    """Build dense int32 lookup arrays from HDF5 lookup tables."""
    venue_to_geo: dict[int, int] = {}
    person_to_geo: dict[int, int] = {}

    if 'lookups/venues' in f:
        for row in f['lookups/venues'][:]:
            venue_to_geo[int(row['venue_id'])] = int(row['geo_unit_id'])
        logger.info(f"  Loaded {len(venue_to_geo)} venue mappings")

    if 'lookups/people' in f:
        for row in f['lookups/people'][:]:
            person_to_geo[int(row['person_id'])] = int(row['geo_unit_id'])
        logger.info(f"  Loaded {len(person_to_geo)} person mappings")

    venue_geo_array: Optional[np.ndarray] = None
    person_geo_array: Optional[np.ndarray] = None

    if venue_to_geo:
        vids = np.array(list(venue_to_geo.keys()), dtype=np.int32)
        vgeos = np.array(list(venue_to_geo.values()), dtype=np.int32)
        max_vid = int(vids.max())
        if max_vid < _MAX_ARRAY_ID:
            venue_geo_array = np.full(max_vid + 1, -1, dtype=np.int32)
            venue_geo_array[vids] = vgeos
            logger.info(f"  Built venue lookup array (size {max_vid + 1:,})")

    if person_to_geo:
        pids = np.array(list(person_to_geo.keys()), dtype=np.int32)
        pgeos = np.array(list(person_to_geo.values()), dtype=np.int32)
        max_pid = int(pids.max())
        if max_pid < _MAX_ARRAY_ID:
            person_geo_array = np.full(max_pid + 1, -1, dtype=np.int32)
            person_geo_array[pids] = pgeos
            logger.info(f"  Built person lookup array (size {max_pid + 1:,})")

    all_geos = set(venue_to_geo.values()) | set(person_to_geo.values())
    n_geo = int(max(all_geos)) + 1 if all_geos else 1

    return venue_geo_array, person_geo_array, n_geo

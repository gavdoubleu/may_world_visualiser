"""Event aggregation, caching, and GeoJSON serialisation."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

import numpy as np

from world_map.events.event_bundle import EventDataBundle

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional Numba JIT kernels
# ---------------------------------------------------------------------------
try:
    from numba import njit
    _NUMBA_AVAILABLE = True
except ImportError:
    _NUMBA_AVAILABLE = False

    def njit(*args, **kwargs):
        def decorator(f):
            return f
        return decorator if (args and callable(args[0])) else decorator


@njit(cache=True)
def _count_venue_and_person(venue_ids, person_ids, venue_geo, person_geo, n_geo):
    counts = np.zeros(n_geo, dtype=np.int32)
    for i in range(len(venue_ids)):
        geo_id = np.int32(-1)
        vid = venue_ids[i]
        if 0 <= vid < len(venue_geo):
            geo_id = venue_geo[vid]
        if geo_id < 0:
            pid = person_ids[i]
            if 0 <= pid < len(person_geo):
                geo_id = person_geo[pid]
        if 0 <= geo_id < n_geo:
            counts[geo_id] += 1
    return counts


@njit(cache=True)
def _count_person_only(person_ids, person_geo, n_geo):
    counts = np.zeros(n_geo, dtype=np.int32)
    for i in range(len(person_ids)):
        pid = person_ids[i]
        if 0 <= pid < len(person_geo):
            geo_id = person_geo[pid]
            if 0 <= geo_id < n_geo:
                counts[geo_id] += 1
    return counts


# ---------------------------------------------------------------------------
# EventAggregator
# ---------------------------------------------------------------------------

_GeoResult = dict[str, Any]
_AggResult = dict[int, _GeoResult]  # internal; int keys


class EventAggregator:
    """
    Computation, caching, and GeoJSON serialisation for simulation events.

    Constructed directly in tests from a hand-built EventDataBundle —
    no HDF5 file required.
    """

    def __init__(
        self,
        bundle: EventDataBundle,
        geo_unit_coords: dict[int, tuple[float, float]],
        geo_unit_population: dict[int, int],
    ):
        self._bundle = bundle
        self._geo_unit_coords = geo_unit_coords
        self._geo_unit_population = geo_unit_population
        self._result_cache: dict[tuple, _AggResult] = {}

        if _NUMBA_AVAILABLE:
            logger.info("Numba JIT available — event aggregation uses compiled kernels")
        else:
            logger.warning("Numba not available — falling back to Python loop for aggregation")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def time_range(self) -> tuple[float, float]:
        return self._bundle.time_min, self._bundle.time_max

    @property
    def geo_unit_coords(self) -> dict[int, tuple[float, float]]:
        return self._geo_unit_coords

    @property
    def geo_unit_population(self) -> dict[int, int]:
        return self._geo_unit_population

    def available_event_types(self) -> list[str]:
        return [k for k, v in self._bundle.events_sorted.items() if len(v) > 0]

    def event_summary(self) -> dict[str, int]:
        return {k: len(v) for k, v in self._bundle.events_sorted.items()}

    def geojson(
        self,
        event_type: str,
        time_start: float,
        time_end: float,
        *,
        method: str = 'count',
        cumulative: bool = False,
    ) -> dict:
        if cumulative:
            raw = self._aggregate(event_type, self._bundle.time_min, time_end, method)
        else:
            raw = self._aggregate(event_type, time_start, time_end, method)

        features = []
        for geo_unit_id, data in raw.items():
            if 'coords' not in data:
                continue
            lat, lon = data['coords']
            features.append({
                'type': 'Feature',
                'properties': {
                    'geo_unit_id': geo_unit_id,
                    'count': data['count'],
                    'rate': data.get('rate', 0.0),
                },
                'geometry': {
                    'type': 'Point',
                    'coordinates': [float(lon), float(lat)],
                },
            })

        return {
            'type': 'FeatureCollection',
            'features': features,
            'properties': {
                'event_type': event_type,
                'time_start': time_start,
                'time_end': time_end,
                'method': method,
                'cumulative': cumulative,
                'total_count': sum(d['count'] for d in raw.values()),
            },
        }

    def timeseries(self, event_type: str) -> list[dict]:
        """Daily event counts as list[{'day': int, 'count': int}]."""
        sorted_arr = self._bundle.events_sorted.get(event_type)
        if sorted_arr is None or len(sorted_arr) == 0:
            return []
        days = np.floor(sorted_arr['time']).astype(int)
        unique, counts = np.unique(days, return_counts=True)
        return [{'day': int(d), 'count': int(c)} for d, c in zip(unique, counts)]

    def aggregated(
        self,
        event_type: str,
        time_start: float,
        time_end: float,
        method: str = 'count',
    ) -> dict[str, dict]:
        """
        JSON-safe aggregation result keyed by str(geo_unit_id).
        Includes count, optional rate, optional coords [lat, lon].
        """
        raw = self._aggregate(event_type, time_start, time_end, method)
        result: dict[str, dict] = {}
        for geo_unit_id, data in raw.items():
            entry: dict[str, Any] = {'count': data['count']}
            if method == 'rate':
                entry['rate'] = data.get('rate', 0.0)
            if 'coords' in data:
                lat, lon = data['coords']
                entry['coords'] = [float(lat), float(lon)]
            result[str(geo_unit_id)] = entry
        return result

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _aggregate(
        self,
        event_type: str,
        time_start: float,
        time_end: float,
        method: str = 'count',
    ) -> _AggResult:
        cache_key = (event_type, round(time_start, 3), round(time_end, 3), method)
        if cache_key in self._result_cache:
            return self._result_cache[cache_key]

        bundle = self._bundle
        times = bundle.events_times.get(event_type)
        sorted_arr = bundle.events_sorted.get(event_type)

        if times is None or sorted_arr is None or len(times) == 0:
            return {}

        start_idx = int(np.searchsorted(times, time_start, side='left'))
        end_idx = int(np.searchsorted(times, time_end, side='right'))

        if start_idx >= end_idx:
            return {}

        filtered = sorted_arr[start_idx:end_idx]

        if 'venue_id' in filtered.dtype.names:
            venue_field = 'venue_id'
        elif 'hospital_id' in filtered.dtype.names:
            venue_field = 'hospital_id'
        else:
            venue_field = None

        counts_arr = None

        if (venue_field is not None
                and bundle.venue_geo_array is not None
                and 'person_id' in filtered.dtype.names
                and bundle.person_geo_array is not None):
            venue_ids = np.ascontiguousarray(filtered[venue_field], dtype=np.int32)
            person_ids = np.ascontiguousarray(filtered['person_id'], dtype=np.int32)
            counts_arr = _count_venue_and_person(
                venue_ids, person_ids,
                bundle.venue_geo_array, bundle.person_geo_array,
                bundle.n_geo)
        elif 'person_id' in filtered.dtype.names and bundle.person_geo_array is not None:
            person_ids = np.ascontiguousarray(filtered['person_id'], dtype=np.int32)
            counts_arr = _count_person_only(person_ids, bundle.person_geo_array, bundle.n_geo)
        else:
            geo_unit_counts: dict[int, int] = defaultdict(int)
            for event in filtered:
                geo_id = -1
                if venue_field:
                    vid = int(event[venue_field])
                    if bundle.venue_geo_array is not None and 0 <= vid < len(bundle.venue_geo_array):
                        geo_id = int(bundle.venue_geo_array[vid])
                if geo_id < 0 and 'person_id' in event.dtype.names:
                    pid = int(event['person_id'])
                    if bundle.person_geo_array is not None and 0 <= pid < len(bundle.person_geo_array):
                        geo_id = int(bundle.person_geo_array[pid])
                if 0 <= geo_id < bundle.n_geo:
                    geo_unit_counts[geo_id] += 1
            result = self._build_result_from_dict(geo_unit_counts, method)
            self._cache_put(cache_key, result)
            return result

        result = self._build_result_from_array(counts_arr, method)
        self._cache_put(cache_key, result)
        return result

    def _build_result_from_array(self, counts_arr: np.ndarray, method: str) -> _AggResult:
        nonzero_geos = np.nonzero(counts_arr)[0]
        result: _AggResult = {}
        for geo_id_np in nonzero_geos:
            geo_id = int(geo_id_np)
            count = int(counts_arr[geo_id])
            entry: _GeoResult = {'count': count}
            if method == 'rate':
                pop = self._geo_unit_population.get(geo_id, 0)
                entry['rate'] = (count / pop) * 100_000 if pop > 0 else 0.0
            if geo_id in self._geo_unit_coords:
                entry['coords'] = self._geo_unit_coords[geo_id]
            result[geo_id] = entry
        return result

    def _build_result_from_dict(self, geo_unit_counts: dict[int, int], method: str) -> _AggResult:
        result: _AggResult = {}
        for geo_unit_id, count in geo_unit_counts.items():
            entry: _GeoResult = {'count': count}
            if method == 'rate':
                pop = self._geo_unit_population.get(geo_unit_id, 0)
                entry['rate'] = (count / pop) * 100_000 if pop > 0 else 0.0
            if geo_unit_id in self._geo_unit_coords:
                entry['coords'] = self._geo_unit_coords[geo_unit_id]
            result[geo_unit_id] = entry
        return result

    def _cache_put(self, key: tuple, result: _AggResult) -> None:
        if len(self._result_cache) >= 256:
            self._result_cache.pop(next(iter(self._result_cache)))
        self._result_cache[key] = result

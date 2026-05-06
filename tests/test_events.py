"""Events route and EventAggregator tests."""

import numpy as np
import pytest

from world_map.events.event_bundle import EventDataBundle
from world_map.events.event_aggregator import EventAggregator
from world_map.testing import WorldBuilder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _infection_dtype():
    return np.dtype([('person_id', np.int32), ('infector_id', np.int32),
                     ('venue_id', np.int32), ('time', np.float32)])


def _make_aggregator(events=None, coords=None, population=None) -> EventAggregator:
    """Build a minimal EventAggregator from synthetic numpy arrays."""
    dt = _infection_dtype()
    if events is None:
        # Two infections: person 0 @ venue 0 @ t=1, person 1 @ venue 0 @ t=5
        arr = np.array([(0, 1, 0, 1.0), (1, 0, 0, 5.0)], dtype=dt)
    else:
        arr = np.array(events, dtype=dt)

    arr_sorted = arr[np.argsort(arr['time'], kind='stable')]
    bundle = EventDataBundle(
        events_sorted={'infections': arr_sorted},
        events_times={'infections': arr_sorted['time'].astype(np.float32)},
        venue_geo_array=np.array([0], dtype=np.int32),   # venue 0 → geo_unit 0
        person_geo_array=np.array([0, 0], dtype=np.int32),  # persons 0,1 → geo_unit 0
        n_geo=1,
        time_min=float(arr['time'].min()),
        time_max=float(arr['time'].max()),
    )
    return EventAggregator(
        bundle,
        geo_unit_coords=coords if coords is not None else {0: (51.5, -0.1)},
        geo_unit_population=population if population is not None else {0: 10_000},
    )


# ---------------------------------------------------------------------------
# Route tests
# ---------------------------------------------------------------------------

def test_events_summary_no_loader(client_for):
    ctx = WorldBuilder().build_context(event_loader=None)
    client = client_for(ctx)
    resp = client.get('/api/events/summary')
    assert resp.status_code == 404
    assert resp.get_json()['error'] == 'Events not loaded'


def test_events_geojson_batch(client_for):
    ctx = WorldBuilder().build_context(event_loader=_make_aggregator())
    client = client_for(ctx)
    resp = client.get('/api/events/geojson/batch?types=infections')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'infections' in data
    assert data['infections']['type'] == 'FeatureCollection'


def test_events_summary_with_loader(client_for):
    ctx = WorldBuilder().build_context(event_loader=_make_aggregator())
    client = client_for(ctx)
    resp = client.get('/api/events/summary')
    assert resp.status_code == 200
    body = resp.get_json()
    assert 'infections' in body['available_types']
    assert body['counts']['infections'] == 2


def test_events_timeseries(client_for):
    ctx = WorldBuilder().build_context(event_loader=_make_aggregator())
    client = client_for(ctx)
    resp = client.get('/api/events/timeseries/infections')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['event_type'] == 'infections'
    assert isinstance(body['data'], list)
    assert all('day' in row and 'count' in row for row in body['data'])


def test_events_aggregated(client_for):
    ctx = WorldBuilder().build_context(event_loader=_make_aggregator())
    client = client_for(ctx)
    resp = client.get('/api/events/aggregated/infections?time_start=0&time_end=10')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['event_type'] == 'infections'
    assert '0' in body['data']           # geo_unit_id 0 as str key
    assert body['data']['0']['count'] == 2


# ---------------------------------------------------------------------------
# EventAggregator boundary tests (no Flask)
# ---------------------------------------------------------------------------

def test_aggregator_time_range():
    agg = _make_aggregator()
    t_min, t_max = agg.time_range
    assert t_min == pytest.approx(1.0)
    assert t_max == pytest.approx(5.0)


def test_aggregator_available_types():
    agg = _make_aggregator()
    assert 'infections' in agg.available_event_types()


def test_aggregator_geojson_windowed():
    agg = _make_aggregator()
    result = agg.geojson('infections', 0.0, 3.0)
    assert result['type'] == 'FeatureCollection'
    assert result['properties']['total_count'] == 1   # only t=1 event in window
    assert len(result['features']) == 1


def test_aggregator_geojson_cumulative():
    agg = _make_aggregator()
    result = agg.geojson('infections', 0.0, 5.0, cumulative=True)
    assert result['properties']['total_count'] == 2


def test_aggregator_aggregated_str_keys():
    agg = _make_aggregator()
    result = agg.aggregated('infections', 0.0, 10.0)
    assert '0' in result
    assert isinstance(list(result.keys())[0], str)
    assert result['0']['count'] == 2


def test_aggregator_timeseries():
    agg = _make_aggregator()
    result = agg.timeseries('infections')
    assert isinstance(result, list)
    assert all(isinstance(row['day'], int) and isinstance(row['count'], int)
               for row in result)


def test_aggregator_empty_event_type():
    agg = _make_aggregator()
    result = agg.aggregated('deaths', 0.0, 10.0)
    assert result == {}


def test_aggregator_rate_method():
    agg = _make_aggregator(population={0: 100_000})
    result = agg.aggregated('infections', 0.0, 10.0, method='rate')
    assert 'rate' in result['0']
    # 2 infections / 100_000 * 100_000 = 2.0
    assert result['0']['rate'] == pytest.approx(2.0)

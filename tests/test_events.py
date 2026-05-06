"""Events route tests."""

from world_map.testing import WorldBuilder


class StubLoader:
    time_max = 10.0

    def get_available_event_types(self):
        return ['infections']

    def get_event_summary(self):
        return {'infections': 42}

    def get_time_range(self):
        return {'min': 0.0, 'max': 10.0}

    def get_events_geojson(self, *, event_type, **_):
        return {'type': 'FeatureCollection', 'features': []}

    def get_daily_events_timeseries(self, event_type):
        import pandas as pd
        return pd.DataFrame({'day': [], 'count': []})

    def aggregate_events_by_geo_unit(self, *, event_type, **_):
        return {}


def test_events_summary_no_loader(client_for):
    ctx = WorldBuilder().build_context(event_loader=None)
    client = client_for(ctx)
    resp = client.get('/api/events/summary')
    assert resp.status_code == 404
    assert resp.get_json()['error'] == 'Events not loaded'


def test_events_geojson_batch_with_stub_loader(client_for):
    ctx = WorldBuilder().build_context(event_loader=StubLoader())
    client = client_for(ctx)
    resp = client.get('/api/events/geojson/batch?types=infections')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'infections' in data
    assert data['infections']['type'] == 'FeatureCollection'

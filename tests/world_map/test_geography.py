"""Geography route tests."""

from tests.support.world_builder import WorldBuilder


def test_geography_levels_empty(client_for):
    ctx = WorldBuilder().build_context()
    client = client_for(ctx)
    resp = client.get('/api/geography/levels')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['levels'] == []
    assert data['units_per_level'] == {}


def test_geography_level_returns_feature(client_for):
    ctx = (
        WorldBuilder()
        .add_unit('Norfolk', level='county', coordinates=(52.6, 1.0), population=100)
        .build_context()
    )
    client = client_for(ctx)
    resp = client.get('/api/geography/county')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['type'] == 'FeatureCollection'
    assert len(data['features']) == 1
    props = data['features'][0]['properties']
    assert props['name'] == 'Norfolk'
    assert props['population'] == 100
    coords = data['features'][0]['geometry']['coordinates']
    assert coords == [1.0, 52.6]  # [lon, lat]


def test_unit_detail_uses_precomputed_stats(client_for):
    from dataclasses import replace
    world = WorldBuilder().add_unit('Norfolk', population=77).build_world()
    base_ctx = WorldBuilder().build_context()
    ctx = replace(base_ctx, world=world)
    client = client_for(ctx)
    resp = client.get('/api/geography/unit/Norfolk')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['population'] == 77
    assert data['slim_mode'] is True


def test_geography_unit_detail_stats(client_for):
    ctx = (
        WorldBuilder()
        .add_unit('Norfolk', level='county', coordinates=(52.6, 1.0), population=5)
        .build_context()
    )
    client = client_for(ctx)
    resp = client.get('/api/geography/unit/Norfolk')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['name'] == 'Norfolk'
    assert data['population'] == 5
    assert data['slim_mode'] is True
    assert '25-34' in data['age_distribution']
    assert 'male' in data['sex_distribution']  # world_reader decodes sex codes to labels


def test_unit_people_returns_paginated_residents(client_for):
    ctx = WorldBuilder().add_unit('Norfolk', population=3).build_context()
    client = client_for(ctx)
    resp = client.get('/api/geography/unit/Norfolk/people')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['total_count'] == 3
    assert len(data['people']) == 3


def test_unit_people_404_on_unknown_unit(client_for):
    ctx = WorldBuilder().build_context()
    client = client_for(ctx)
    resp = client.get('/api/geography/unit/NoSuchUnit/people')
    assert resp.status_code == 404


def test_unit_by_id_resolves_name(client_for):
    ctx = WorldBuilder().add_unit('Norfolk', population=3).build_context()
    client = client_for(ctx)
    unit_id = ctx.world.geography.get_unit('Norfolk').id
    resp = client.get(f'/api/geography/unit_by_id/{unit_id}')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['name'] == 'Norfolk'
    assert data['id'] == unit_id


def test_unit_by_id_404_on_unknown_id(client_for):
    ctx = WorldBuilder().build_context()
    client = client_for(ctx)
    resp = client.get('/api/geography/unit_by_id/9999')
    assert resp.status_code == 404

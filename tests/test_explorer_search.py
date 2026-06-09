"""TDD tests for geo-unit search: GeographyManager.search_units_by_name
and the /api/explorer/geo_unit/search endpoint."""

import pytest
from world_map.testing import WorldBuilder
from world_explorer.app import create_app


def _client(world):
    return create_app(world, world._builder_hdf5_path).test_client()


# ── GeographyManager.search_units_by_name ────────────────────────────────────

def test_search_units_by_name_single_match():
    world = WorldBuilder().add_unit('Norfolk', population=2).build_world()
    results = world.geography.search_units_by_name('Norfolk')
    assert len(results) == 1
    assert results[0]['name'] == 'Norfolk'
    assert 'id' in results[0]
    assert 'level' in results[0]
    assert 'parent_name' in results[0]
    assert results[0]['parent_name'] is None


def test_search_units_by_name_case_insensitive():
    world = WorldBuilder().add_unit('Norfolk', population=1).build_world()
    assert len(world.geography.search_units_by_name('norfolk')) == 1
    assert len(world.geography.search_units_by_name('NORFOLK')) == 1
    assert len(world.geography.search_units_by_name('NoRfOlK')) == 1


def test_search_units_by_name_multiple_matches():
    world = (
        WorldBuilder()
        .add_unit('England', level='country', population=0)
        .add_unit('Springfield', level='region', population=5, parent='England')
        .add_unit('Wales', level='country', population=0)
        .add_unit('Springfield', level='region', population=3, parent='Wales')
        .build_world()
    )
    results = world.geography.search_units_by_name('Springfield')
    assert len(results) == 2
    names = {r['name'] for r in results}
    assert names == {'Springfield'}
    parent_names = {r['parent_name'] for r in results}
    assert parent_names == {'England', 'Wales'}


def test_search_units_by_name_no_match():
    world = WorldBuilder().add_unit('Norfolk', population=1).build_world()
    assert world.geography.search_units_by_name('Nonexistent') == []


def test_search_units_by_name_includes_parent_name():
    world = (
        WorldBuilder()
        .add_unit('England', level='country', population=0)
        .add_unit('Norfolk', level='region', population=5, parent='England')
        .build_world()
    )
    results = world.geography.search_units_by_name('Norfolk')
    assert results[0]['parent_name'] == 'England'


# ── /api/explorer/geo_unit/search ────────────────────────────────────────────

def test_search_endpoint_returns_list():
    world = WorldBuilder().add_unit('Norfolk', population=2).build_world()
    resp = _client(world).get('/api/explorer/geo_unit/search?name=Norfolk')
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]['name'] == 'Norfolk'


def test_search_endpoint_empty_for_unknown():
    world = WorldBuilder().add_unit('Norfolk', population=1).build_world()
    resp = _client(world).get('/api/explorer/geo_unit/search?name=Nowhere')
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_search_endpoint_missing_param():
    world = WorldBuilder().add_unit('Norfolk', population=1).build_world()
    resp = _client(world).get('/api/explorer/geo_unit/search')
    assert resp.status_code == 400

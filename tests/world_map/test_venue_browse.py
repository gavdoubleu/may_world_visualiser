"""Route tests for the venue_browse blueprint (Venues/Venue Detail/locate)."""

from tests.support.world_builder import WorldBuilder


def test_unit_venues_returns_paginated_venues(client_for):
    ctx = (
        WorldBuilder()
        .add_unit('Norfolk', population=2)
        .add_venue('Norwich School', 'school', 'Norfolk', coordinates=(52.6, 1.3))
        .add_venue('Norwich Hospital', 'hospital', 'Norfolk')
        .build_context()
    )
    client = client_for(ctx)
    resp = client.get('/api/geography/unit/Norfolk/venues')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['total_count'] == 2
    names = {v['name'] for v in data['venues']}
    assert names == {'Norwich School', 'Norwich Hospital'}


def test_unit_venues_filters_by_type(client_for):
    ctx = (
        WorldBuilder()
        .add_unit('Norfolk', population=0)
        .add_venue('Norwich School', 'school', 'Norfolk')
        .add_venue('Norwich Hospital', 'hospital', 'Norfolk')
        .build_context()
    )
    client = client_for(ctx)
    resp = client.get('/api/geography/unit/Norfolk/venues?type=hospital')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['total_count'] == 1
    assert data['venues'][0]['name'] == 'Norwich Hospital'


def test_unit_venues_404_on_unknown_unit(client_for):
    ctx = WorldBuilder().build_context()
    client = client_for(ctx)
    resp = client.get('/api/geography/unit/NoSuchUnit/venues')
    assert resp.status_code == 404


def test_venue_detail_returns_full_shape(client_for):
    ctx = (
        WorldBuilder()
        .add_unit('Norfolk')
        .add_venue('Norwich School', 'school', 'Norfolk', coordinates=(52.6, 1.3))
        .build_context()
    )
    client = client_for(ctx)
    resp = client.get('/api/geography/venue/0/detail')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['name'] == 'Norwich School'
    assert data['type'] == 'school'
    assert data['geo_unit'] == 'Norfolk'
    assert data['coordinates'] == [52.6, 1.3]


def test_venue_detail_404_on_unknown_id(client_for):
    ctx = WorldBuilder().build_context()
    client = client_for(ctx)
    resp = client.get('/api/geography/venue/999/detail')
    assert resp.status_code == 404


def test_venue_children_paginated_for_parent_venue(client_for):
    ctx = (
        WorldBuilder()
        .add_unit('Norfolk')
        .add_venue('Norwich Estate', 'household', 'Norfolk')
        .add_venue('Flat 1', 'household', 'Norfolk', parent='Norwich Estate')
        .add_venue('Flat 2', 'household', 'Norfolk', parent='Norwich Estate')
        .build_context()
    )
    client = client_for(ctx)
    resp = client.get('/api/geography/venue/0/children')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['total_count'] == 2
    names = {v['name'] for v in data['venues']}
    assert names == {'Flat 1', 'Flat 2'}


def test_venue_children_empty_for_leaf_venue(client_for):
    ctx = (
        WorldBuilder()
        .add_unit('Norfolk')
        .add_venue('Norwich School', 'school', 'Norfolk')
        .build_context()
    )
    client = client_for(ctx)
    resp = client.get('/api/geography/venue/0/children')
    assert resp.status_code == 200
    assert resp.get_json()['total_count'] == 0


def test_locate_venue_resolves_owning_geo_unit(client_for):
    ctx = (
        WorldBuilder()
        .add_unit('Norfolk')
        .add_venue('Norwich School', 'school', 'Norfolk')
        .build_context()
    )
    client = client_for(ctx)
    resp = client.get('/api/geography/venue/0/locate')
    assert resp.status_code == 200
    data = resp.get_json()
    unit = ctx.world.geography.get_unit('Norfolk')
    assert data['geo_unit_id'] == unit.id


def test_locate_venue_404_on_unknown_id(client_for):
    ctx = WorldBuilder().build_context()
    client = client_for(ctx)
    resp = client.get('/api/geography/venue/999/locate')
    assert resp.status_code == 404


def test_locate_person_resolves_owning_geo_unit(client_for):
    ctx = WorldBuilder().add_unit('Norfolk', population=1).build_context()
    client = client_for(ctx)
    resp = client.get('/api/geography/person/0/locate')
    assert resp.status_code == 200
    data = resp.get_json()
    unit = ctx.world.geography.get_unit('Norfolk')
    assert data['geo_unit_id'] == unit.id


def test_locate_person_404_on_unknown_id(client_for):
    ctx = WorldBuilder().build_context()
    client = client_for(ctx)
    resp = client.get('/api/geography/person/999/locate')
    assert resp.status_code == 404


def test_venue_members_paginated_empty_when_no_subsets(client_for):
    ctx = (
        WorldBuilder()
        .add_unit('Norfolk')
        .add_venue('Norwich School', 'school', 'Norfolk')
        .build_context()
    )
    client = client_for(ctx)
    resp = client.get('/api/geography/venue/0/members')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['venue_id'] == 0
    assert data['subsets'] == []


def test_venue_members_returns_subset_with_members(client_for):
    ctx = (
        WorldBuilder()
        .add_unit('Norfolk', population=3)
        .add_venue('Norwich School', 'school', 'Norfolk')
        .add_subset('Norwich School', 'pupils', [0, 1, 2])
        .build_context()
    )
    client = client_for(ctx)
    resp = client.get('/api/geography/venue/0/members')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['venue_id'] == 0
    assert data['venue_name'] == 'Norwich School'
    assert len(data['subsets']) == 1
    subset = data['subsets'][0]
    assert subset['name'] == 'pupils'
    assert subset['total'] == 3
    member_ids = {m['id'] for m in subset['members']}
    assert member_ids == {0, 1, 2}


def test_venue_members_paginates_within_subset(client_for):
    ctx = (
        WorldBuilder()
        .add_unit('Norfolk', population=5)
        .add_venue('Norwich School', 'school', 'Norfolk')
        .add_subset('Norwich School', 'pupils', [0, 1, 2, 3, 4])
        .build_context()
    )
    client = client_for(ctx)
    resp = client.get('/api/geography/venue/0/members?page=1&per_page=2')
    assert resp.status_code == 200
    subset = resp.get_json()['subsets'][0]
    assert subset['total'] == 5
    assert subset['total_pages'] == 3
    assert len(subset['members']) == 2


def test_venue_members_filters_by_subset_name(client_for):
    ctx = (
        WorldBuilder()
        .add_unit('Norfolk', population=4)
        .add_venue('Norwich School', 'school', 'Norfolk')
        .add_subset('Norwich School', 'pupils', [0, 1])
        .add_subset('Norwich School', 'staff', [2, 3])
        .build_context()
    )
    client = client_for(ctx)
    resp = client.get('/api/geography/venue/0/members?subset=staff')
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data['subsets']) == 1
    assert data['subsets'][0]['name'] == 'staff'
    member_ids = {m['id'] for m in data['subsets'][0]['members']}
    assert member_ids == {2, 3}

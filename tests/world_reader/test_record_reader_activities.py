"""Tests for RecordReader.load_person_activities."""

import numpy as np
import pytest
import h5py

from tests.support.world_builder import WorldBuilder
from world_reader import RecordReader


@pytest.fixture
def loader():
    """RecordReader over a builder-generated world, with one activity grafted
    on (the builder has no add_activity API — activity_mappings datasets are
    appended to the builder's own HDF5 file after the fact).

    Two people: id=5 at array index 0, id=3 at array index 1.
    Person id=5 has one activity: act_type=0 ('work'), venue row=0
      (logical venue id=7, 'office'), subset_pos=0 ('desk').
    Person id=3 has no activities.

    Logical venue id (7) deliberately differs from its row index (0), so a
    test that asserts on the logical id catches row-index leaks.
    """
    world = (WorldBuilder()
             .add_unit('Geo', population=2)
             .add_venue('office', 'workplace', geo_unit='Geo')
             .add_subset('office', 'desk', member_person_ids=[5])
             .with_person_id_to_idx(np.array([5, 3], dtype=np.int64))
             .with_venue_id_to_idx(np.array([7], dtype=np.int64))
             .build_world())

    dt = h5py.string_dtype()
    with h5py.File(world._builder_hdf5_path, 'a') as f:
        f.create_dataset('activity_mappings/activity_map/activity_offsets',
                         data=np.array([0, 1], dtype=np.int64))
        f.create_dataset('activity_mappings/activity_map/activity_data',
                         data=np.array([[0, 0, 0, 0]], dtype=np.int32))
        f.create_dataset('activity_mappings/activity_map/activity_names',
                         data=np.array([b'work'], dtype=dt))
    world.activity_names = ['work']

    record_reader = RecordReader(world._builder_hdf5_path, world)
    record_reader._test_world = world  # keep world's tmpdir (and its .h5) alive
    return record_reader


def test_load_person_activities_returns_correct_record(loader):
    activities = loader.load_person_activities(5)
    assert activities is not None
    assert len(activities) == 1
    act = activities[0]
    assert act['activity_name'] == 'work'
    assert act['venue_id']      == 7  # logical id (venues/ids), not row index
    assert act['venue_name']    == 'office'
    assert act['venue_type']    == 'workplace'
    assert act['subset_name']   == 'desk'


def test_load_person_activities_empty_for_no_activities(loader):
    activities = loader.load_person_activities(3)
    assert activities == []


def test_load_person_activities_returns_none_for_unknown_id(loader):
    assert loader.load_person_activities(999) is None


def test_load_person_activities_high_count_repeated_venues_preserves_order():
    """A person with many activities against a small, repeated set of venues
    (the case the np.unique/return_inverse dedup-and-scatter rewrite targets),
    visited in deliberately non-monotonic order.

    Exercises two risks specific to the dedup rewrite: (1) values gathered
    via the deduped/sorted unique-venue read must scatter back to the
    *correct* original row, and (2) the returned list's order must match
    activity_data row order exactly, not sorted-by-venue order.
    """
    venue_names      = ['home', 'work', 'school', 'gym']
    venue_types      = ['household', 'workplace', 'education', 'leisure']
    subset_names     = ['residents', 'desk', 'class', 'members']

    world = WorldBuilder().add_unit('Geo', population=1)
    for venue_name, venue_type, subset_name in zip(venue_names, venue_types, subset_names):
        world = world.add_venue(venue_name, venue_type, geo_unit='Geo')
        world = world.add_subset(venue_name, subset_name, member_person_ids=[0])
    world = world.build_world()

    # non-monotonic, repeated venue-row visit order — deliberately not sorted
    venue_row_sequence = ([3, 0, 2, 0, 1, 3, 0] * 9)[:60]
    activity_data = np.array(
        [[0, 0, venue_row, 0] for venue_row in venue_row_sequence], dtype=np.int32)

    dt = h5py.string_dtype()
    with h5py.File(world._builder_hdf5_path, 'a') as f:
        f.create_dataset('activity_mappings/activity_map/activity_offsets',
                         data=np.array([0], dtype=np.int64))
        f.create_dataset('activity_mappings/activity_map/activity_data', data=activity_data)
        f.create_dataset('activity_mappings/activity_map/activity_names',
                         data=np.array([b'commute'], dtype=dt))
    world.activity_names = ['commute']

    record_reader = RecordReader(world._builder_hdf5_path, world)
    record_reader._test_world = world  # keep world's tmpdir (and its .h5) alive

    activities = record_reader.load_person_activities(0)
    assert activities is not None
    assert len(activities) == len(venue_row_sequence)

    for activity, venue_row in zip(activities, venue_row_sequence):
        assert activity['activity_name']  == 'commute'
        assert activity['venue_id']       == venue_row  # default builder ids == row index
        assert activity['venue_name']     == venue_names[venue_row]
        assert activity['venue_type']     == venue_types[venue_row]
        assert activity['subset_name']    == subset_names[venue_row]

    # order must match activity_data row order, not sorted-by-venue order
    assert [a['venue_name'] for a in activities] == [venue_names[v] for v in venue_row_sequence]


# --- lazy subtree-backed reads (build_world_store end-to-end) ---

from world_reader import build_world_store


@pytest.fixture
def subtree_world_h5(tmp_path):
    """Minimal world: parent 'London' (geo_id 0) → child 'Camden' (geo_id 1).

    People: 2 in London (ids 0,1), 1 in Camden (id 2).
    Venues: venue 0 'Pub' in London, venue 1 'School' in Camden.
    venue 0 has one subset 'regulars' (3 members), venue 1 has none.
    """
    h5_path = tmp_path / 'subtree_world.h5'
    dt = h5py.string_dtype()
    with h5py.File(h5_path, 'w') as f:
        # geography: 2 units, Camden's parent is London
        f.create_dataset('geography/ids',        data=np.array([0, 1], dtype=np.int32))
        f.create_dataset('geography/parent_ids',  data=np.array([-1, 0], dtype=np.int32))
        f.create_dataset('geography/levels',      data=np.array([0, 1], dtype=np.int32))
        f.create_dataset('metadata/names/geography',
                         data=np.array([b'London', b'Camden'], dtype=dt))
        f.create_dataset('metadata/registries/geo_levels',
                         data=np.array([b'city', b'borough'], dtype=dt))

        # population: ids 0,1 in London(0); id 2 in Camden(1)
        f.create_dataset('population/ids',          data=np.array([0, 1, 2], dtype=np.int32))
        f.create_dataset('population/ages',         data=np.array([30, 40, 5], dtype=np.int32))
        f.create_dataset('population/sexes',        data=np.array([0, 1, 0], dtype=np.uint8))
        f.create_dataset('population/geo_unit_ids', data=np.array([0, 0, 1], dtype=np.int32))

        # venues: venue 0 in London, venue 1 in Camden
        f.create_dataset('venues/ids',          data=np.array([0, 1], dtype=np.int32))
        f.create_dataset('venues/geo_unit_ids', data=np.array([0, 1], dtype=np.int32))
        f.create_dataset('venues/types',        data=np.array([0, 1], dtype=np.uint8))
        f.create_dataset('venues/latitudes',    data=np.array([51.5, np.nan], dtype=np.float32))
        f.create_dataset('venues/longitudes',   data=np.array([-0.1, np.nan], dtype=np.float32))
        f.create_dataset('metadata/names/venues',
                         data=np.array([b'Pub', b'School'], dtype=dt))
        f.create_dataset('metadata/registries/venue_types',
                         data=np.array([b'bar', b'education'], dtype=dt))

        # subsets: one subset on venue 0
        f.create_dataset('venues/subsets/venue_ids',     data=np.array([0], dtype=np.int32))
        f.create_dataset('venues/subsets/member_counts', data=np.array([3], dtype=np.int32))
        f.create_dataset('metadata/names/subsets',
                         data=np.array([b'regulars'], dtype=dt))
    return h5_path


@pytest.fixture
def subtree_loader(subtree_world_h5):
    world  = build_world_store(str(subtree_world_h5))
    loader = RecordReader(str(subtree_world_h5), world)
    return world, loader


def test_load_unit_people_includes_descendants(subtree_loader):
    world, loader = subtree_loader
    london_id = world.geography.get_unit('London').id
    camden_id = world.geography.get_unit('Camden').id
    # London subtree = London(2) + Camden(1) = 3 people
    london = loader.load_unit_people(london_id, page=1, per_page=50)
    assert london['total_count'] == 3
    assert {p['id'] for p in london['people']} == {0, 1, 2}
    # Camden alone = 1 person
    camden = loader.load_unit_people(camden_id, page=1, per_page=50)
    assert camden['total_count'] == 1
    assert camden['people'][0]['id'] == 2


def test_load_unit_people_pagination(subtree_loader):
    world, loader = subtree_loader
    london_id = world.geography.get_unit('London').id
    page1 = loader.load_unit_people(london_id, page=1, per_page=2)
    page2 = loader.load_unit_people(london_id, page=2, per_page=2)
    assert page1['total_pages'] == 2
    assert len(page1['people']) == 2 and len(page2['people']) == 1
    ids = {p['id'] for p in page1['people']} | {p['id'] for p in page2['people']}
    assert ids == {0, 1, 2}


def test_load_unit_venues_subtree_and_filter(subtree_loader):
    world, loader = subtree_loader
    london_id = world.geography.get_unit('London').id
    allv = loader.load_unit_venues(london_id, page=1, per_page=50, type_filter=None)
    assert allv['total_count'] == 2
    assert {v['name'] for v in allv['venues']} == {'Pub', 'School'}
    bars = loader.load_unit_venues(london_id, page=1, per_page=50, type_filter='bar')
    assert bars['total_count'] == 1
    pub = bars['venues'][0]
    assert pub['name'] == 'Pub' and pub['type'] == 'bar'
    assert pub['coordinates'] == [pytest.approx(51.5), pytest.approx(-0.1)]
    assert pub['subsets'] == [{'name': 'regulars', 'num_members': 3}]


def test_load_venue_detail(subtree_loader):
    _, loader = subtree_loader
    pub = loader.load_venue_detail(0)
    assert pub['name'] == 'Pub' and pub['type'] == 'bar' and pub['geo_unit'] == 'London'
    assert pub['subsets'] == [{'name': 'regulars', 'num_members': 3}]
    school = loader.load_venue_detail(1)
    assert school['name'] == 'School' and school['coordinates'] is None
    assert loader.load_venue_detail(99) is None


def test_load_person_slim(subtree_loader):
    _, loader = subtree_loader
    person = loader.load_person_slim(2)
    assert person['id'] == 2 and person['age'] == 5
    assert person['geographical_unit']['name'] == 'Camden'
    assert loader.load_person_slim(999) is None

"""Tests for ExplorerLoader.load_person_activities."""

import numpy as np
import pytest
import h5py

from world_map.testing import WorldBuilder
from world_explorer.explorer_loader import ExplorerLoader


@pytest.fixture
def person_activities_h5(tmp_path):
    """Minimal HDF5 for testing load_person_activities.

    Two people: id=5 at array index 0, id=3 at array index 1.
    Person id=5 has one activity: act_type=0 ('work'), venue=0 ('office'),
      subset_pos=0 ('desk'), venue geo_unit=10.
    Person id=3 has no activities.
    """
    h5_path = tmp_path / 'activities_test.h5'
    with h5py.File(h5_path, 'w') as f:
        # population: array order [id=5, id=3]
        f.create_dataset('population/ids',  data=np.array([5, 3], dtype=np.int32))

        # activity offsets: person at idx 0 has activities [0,1), idx 1 has [1,1)
        f.create_dataset('activity_mappings/activity_map/activity_offsets',
                         data=np.array([0, 1], dtype=np.int64))
        # activity_data row: [person_array_idx, act_type_idx, venue_id, subset_pos]
        f.create_dataset('activity_mappings/activity_map/activity_data',
                         data=np.array([[0, 0, 0, 0]], dtype=np.int32))

        dt = h5py.string_dtype()
        f.create_dataset('activity_mappings/activity_map/activity_names',
                         data=np.array([b'work'], dtype=dt))
        f.create_dataset('metadata/names/venues',
                         data=np.array([b'office'], dtype=dt))
        f.create_dataset('metadata/names/subsets',
                         data=np.array([b'desk'], dtype=dt))
        f.create_dataset('metadata/registries/venue_types',
                         data=np.array([b'workplace'], dtype=dt))
        f.create_dataset('venues/types',
                         data=np.array([0], dtype=np.int32))
        f.create_dataset('venues/geo_unit_ids',
                         data=np.array([10], dtype=np.int32))

        # subset venue mapping: venue 0 has one subset at row 0
        f.create_dataset('venues/subsets/venue_ids',
                         data=np.array([0], dtype=np.int32))
    return h5_path


@pytest.fixture
def loader(person_activities_h5):
    # person_id_to_idx: id5→idx0, id3→idx1 (array size must cover max id=5)
    person_id_to_idx = np.full(6, -1, dtype=np.int64)
    person_id_to_idx[5] = 0
    person_id_to_idx[3] = 1
    subset_venue_ids = np.array([0], dtype=np.int64)
    geography = WorldBuilder().build_world().geography
    return ExplorerLoader(person_activities_h5, person_id_to_idx, subset_venue_ids, geography)


def test_load_person_activities_returns_correct_record(loader):
    activities = loader.load_person_activities(5)
    assert activities is not None
    assert len(activities) == 1
    act = activities[0]
    assert act['activity_name'] == 'work'
    assert act['venue_id']      == 0
    assert act['venue_name']    == 'office'
    assert act['venue_type']    == 'workplace'
    assert act['subset_name']   == 'desk'


def test_load_person_activities_empty_for_no_activities(loader):
    activities = loader.load_person_activities(3)
    assert activities == []


def test_load_person_activities_returns_none_for_unknown_id(loader):
    assert loader.load_person_activities(999) is None


# --- lazy subtree-backed reads (load_explorer_world end-to-end) ---

from world_explorer.explorer_world_loader import load_explorer_world
from world_explorer.explorer_loader import ExplorerLoader as _EL


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
    world = load_explorer_world(str(subtree_world_h5))
    loader = _EL(str(subtree_world_h5), world.person_id_to_idx,
                 world.subset_venue_ids, world.geography, world.subtree_index)
    return world, loader


def test_load_unit_people_includes_descendants(subtree_loader):
    _, loader = subtree_loader
    # London subtree = London(2) + Camden(1) = 3 people
    london = loader.load_unit_people('London', page=1, per_page=50)
    assert london['total_count'] == 3
    assert {p['id'] for p in london['people']} == {0, 1, 2}
    # Camden alone = 1 person
    camden = loader.load_unit_people('Camden', page=1, per_page=50)
    assert camden['total_count'] == 1
    assert camden['people'][0]['id'] == 2


def test_load_unit_people_pagination(subtree_loader):
    _, loader = subtree_loader
    page1 = loader.load_unit_people('London', page=1, per_page=2)
    page2 = loader.load_unit_people('London', page=2, per_page=2)
    assert page1['total_pages'] == 2
    assert len(page1['people']) == 2 and len(page2['people']) == 1
    ids = {p['id'] for p in page1['people']} | {p['id'] for p in page2['people']}
    assert ids == {0, 1, 2}


def test_load_unit_venues_subtree_and_filter(subtree_loader):
    _, loader = subtree_loader
    allv = loader.load_unit_venues('London', page=1, per_page=50, type_filter=None)
    assert allv['total_count'] == 2
    assert {v['name'] for v in allv['venues']} == {'Pub', 'School'}
    bars = loader.load_unit_venues('London', page=1, per_page=50, type_filter='bar')
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

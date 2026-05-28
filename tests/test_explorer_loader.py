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


# --- collect_unit_venues ---

from world_map.core.world_data import GeoUnit, Venue


def _make_loader(geography):
    person_id_to_idx = np.array([], dtype=np.int64)
    subset_venue_ids = np.array([], dtype=np.int64)
    return ExplorerLoader.__new__(ExplorerLoader), geography


def _loader_with_geography(geography):
    person_id_to_idx = np.array([], dtype=np.int64)
    subset_venue_ids = np.array([], dtype=np.int64)
    loader = ExplorerLoader.__new__(ExplorerLoader)
    loader._geography = geography
    loader._hdf5_path = ''
    loader._person_id_to_idx = person_id_to_idx
    loader._subset_venue_ids = subset_venue_ids
    return loader


def test_collect_unit_venues_single_unit():
    world = WorldBuilder().add_unit('London').build_world()
    unit = world.geography.get_unit('London')
    unit.venues.append(Venue(1, 'Pub', 'bar'))
    unit.venues.append(Venue(2, 'Hospital', 'healthcare'))

    loader = _loader_with_geography(world.geography)
    venues = loader.collect_unit_venues('London')
    assert len(venues) == 2
    assert {v.name for v in venues} == {'Pub', 'Hospital'}


def test_collect_unit_venues_includes_children():
    world = WorldBuilder().add_unit('London').add_unit('Camden').build_world()
    geo = world.geography
    parent = geo.get_unit('London')
    child  = geo.get_unit('Camden')
    child.parent = parent
    parent.children.append(child)

    parent.venues.append(Venue(1, 'Gallery', 'culture'))
    child.venues.append(Venue(2, 'School', 'education'))

    loader = _loader_with_geography(geo)
    venues = loader.collect_unit_venues('London')
    assert {v.name for v in venues} == {'Gallery', 'School'}


def test_collect_unit_venues_unknown_unit_returns_empty():
    world = WorldBuilder().add_unit('London').build_world()
    loader = _loader_with_geography(world.geography)
    assert loader.collect_unit_venues('Atlantis') == []

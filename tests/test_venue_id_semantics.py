"""Regression tests: RecordReader venue methods must translate logical
venue IDs (venues/ids) to/from HDF5 row indices at the API boundary, not
treat the logical ID as a row index. Covers the case where venues/ids has
true gaps (e.g. a subset-of-a-larger-world file where max ID > row count)."""

import numpy as np
import pytest
import h5py

from world_reader import RecordReader, build_world_store


@pytest.fixture
def gapped_venues_h5(tmp_path):
    """Three venues whose logical IDs are gapped and exceed the row count.

    Row 0 'Pub'    logical id 10, in London (geo_id 0), type 'bar', ParentVenue
    Row 1 'School' logical id 25, in Camden (geo_id 1), type 'education'
    Row 2 'Cellar' logical id 7,  child of row 0 (Pub), type 'bar'

    Internal cross-references (subsets/venue_ids, parent_ids, members_flat)
    stay row/array-index aligned — only venues/ids and population/ids carry
    the logical, gapped values.
    """
    h5_path = tmp_path / 'gapped_venues.h5'
    dt = h5py.string_dtype()
    with h5py.File(h5_path, 'w') as f:
        f.create_dataset('geography/ids',        data=np.array([0, 1], dtype=np.int32))
        f.create_dataset('geography/parent_ids', data=np.array([-1, 0], dtype=np.int32))
        f.create_dataset('geography/levels',     data=np.array([0, 1], dtype=np.int32))
        f.create_dataset('metadata/names/geography',
                         data=np.array([b'London', b'Camden'], dtype=dt))
        f.create_dataset('metadata/registries/geo_levels',
                         data=np.array([b'city', b'borough'], dtype=dt))

        f.create_dataset('population/ids',          data=np.array([0, 1], dtype=np.int32))
        f.create_dataset('population/ages',         data=np.array([30, 40], dtype=np.int32))
        f.create_dataset('population/sexes',        data=np.array([0, 1], dtype=np.uint8))
        f.create_dataset('population/geo_unit_ids', data=np.array([0, 1], dtype=np.int32))

        # gapped, non-contiguous logical venue IDs (max 25 > row count 3)
        f.create_dataset('venues/ids',          data=np.array([10, 25, 7], dtype=np.int32))
        f.create_dataset('venues/geo_unit_ids', data=np.array([0, 1, 0], dtype=np.int32))
        f.create_dataset('venues/types',        data=np.array([0, 1, 0], dtype=np.uint8))
        f.create_dataset('venues/parent_ids',   data=np.array([-1, -1, 0], dtype=np.int32))
        f.create_dataset('venues/latitudes',
                         data=np.array([51.5, 51.6, 51.55], dtype=np.float32))
        f.create_dataset('venues/longitudes',
                         data=np.array([-0.1, -0.2, -0.15], dtype=np.float32))
        f.create_dataset('metadata/names/venues',
                         data=np.array([b'Pub', b'School', b'Cellar'], dtype=dt))
        f.create_dataset('metadata/registries/venue_types',
                         data=np.array([b'bar', b'education'], dtype=dt))

        # subset references stay row-index aligned: row 0 ('Pub') has 1 subset
        # whose members are logical person IDs [0, 1] (population/ids order)
        f.create_dataset('venues/subsets/venue_ids',       data=np.array([0], dtype=np.int32))
        f.create_dataset('venues/subsets/member_counts',   data=np.array([2], dtype=np.int32))
        f.create_dataset('venues/subsets/members_offsets', data=np.array([0, 2], dtype=np.int64))
        f.create_dataset('venues/subsets/members_flat',    data=np.array([0, 1], dtype=np.int32))
        f.create_dataset('metadata/names/subsets',
                         data=np.array([b'regulars'], dtype=dt))
    return h5_path


@pytest.fixture
def gapped_venues_loader(gapped_venues_h5):
    world = build_world_store(str(gapped_venues_h5))
    return RecordReader(str(gapped_venues_h5), world)


def test_load_venue_detail_returns_logical_id_not_row_index(gapped_venues_loader):
    pub = gapped_venues_loader.load_venue_detail(10)
    assert pub['id'] == 10
    assert pub['name'] == 'Pub'
    assert pub['subsets'] == [{'name': 'regulars', 'num_members': 2}]

    school = gapped_venues_loader.load_venue_detail(25)
    assert school['id'] == 25
    assert school['name'] == 'School'

    # row index 0 is not a valid logical ID in this world (smallest is 10)
    assert gapped_venues_loader.load_venue_detail(0) is None


@pytest.fixture
def gapped_persons_h5(tmp_path):
    """Two people whose logical IDs have a TRUE gap: max ID (100) > row count
    (2) — the "subset of a larger world" case. The old build_world_store
    construction (`np.empty_like(ids); arr[ids] = arange(N)`) raises IndexError
    the moment any ID >= N; this fixture is the regression guard against that."""
    h5_path = tmp_path / 'gapped_persons.h5'
    dt = h5py.string_dtype()
    with h5py.File(h5_path, 'w') as f:
        f.create_dataset('geography/ids',        data=np.array([0], dtype=np.int32))
        f.create_dataset('geography/parent_ids', data=np.array([-1], dtype=np.int32))
        f.create_dataset('geography/levels',     data=np.array([0], dtype=np.int32))
        f.create_dataset('metadata/names/geography', data=np.array([b'London'], dtype=dt))
        f.create_dataset('metadata/registries/geo_levels', data=np.array([b'city'], dtype=dt))

        f.create_dataset('population/ids',          data=np.array([100, 5], dtype=np.int32))
        f.create_dataset('population/ages',         data=np.array([30, 40], dtype=np.int32))
        f.create_dataset('population/sexes',        data=np.array([0, 1], dtype=np.uint8))
        f.create_dataset('population/geo_unit_ids', data=np.array([0, 0], dtype=np.int32))

        f.create_dataset('venues/ids',          data=np.array([], dtype=np.int32))
        f.create_dataset('venues/geo_unit_ids', data=np.array([], dtype=np.int32))
        f.create_dataset('venues/types',        data=np.array([], dtype=np.uint8))
        f.create_dataset('venues/latitudes',    data=np.array([], dtype=np.float32))
        f.create_dataset('venues/longitudes',   data=np.array([], dtype=np.float32))
        f.create_dataset('metadata/names/venues', data=np.array([], dtype=dt))
        f.create_dataset('metadata/registries/venue_types', data=np.array([], dtype=dt))
        f.create_dataset('venues/subsets/venue_ids',     data=np.array([], dtype=np.int32))
        f.create_dataset('venues/subsets/member_counts', data=np.array([], dtype=np.int32))
    return h5_path


@pytest.fixture
def gapped_persons_loader(gapped_persons_h5):
    world = build_world_store(str(gapped_persons_h5))
    return RecordReader(str(gapped_persons_h5), world)


def test_person_id_to_idx_handles_true_gaps(gapped_persons_loader):
    """Regression guard: building person_id_to_idx must not IndexError when
    logical IDs exceed the row count (it used to, via np.empty_like(ids))."""
    alice = gapped_persons_loader.load_person_slim(100)
    assert alice['age'] == 30
    bob = gapped_persons_loader.load_person_slim(5)
    assert bob['age'] == 40

    # row index 0 is not a valid logical ID here (smallest logical id is 5)
    assert gapped_persons_loader.load_person_slim(0) is None


def test_load_venues_by_type_returns_logical_ids(gapped_venues_loader):
    bars = gapped_venues_loader.load_venues_by_type('bar')
    assert {venue['id'] for venue in bars} == {10, 7}  # Pub and Cellar

    schools = gapped_venues_loader.load_venues_by_type('education')
    assert [venue['id'] for venue in schools] == [25]
    assert schools[0]['name'] == 'School'


def test_load_venue_children_returns_logical_ids(gapped_venues_loader):
    children = gapped_venues_loader.load_venue_children(10, page=1, per_page=50)
    assert children['parent_id'] == 10
    assert [venue['id'] for venue in children['venues']] == [7]
    assert children['venues'][0]['name'] == 'Cellar'

    # School (25) has no children
    assert gapped_venues_loader.load_venue_children(25, page=1, per_page=50)['venues'] == []


def test_locate_venue_resolves_logical_id(gapped_venues_loader):
    pub = gapped_venues_loader.locate_venue(10, per_page=50)
    assert pub['geo_unit'] == 'London'
    assert pub['venue_type'] == 'bar'

    school = gapped_venues_loader.locate_venue(25, per_page=50)
    assert school['geo_unit'] == 'Camden'
    assert school['venue_type'] == 'education'

    # row index 1 is not a valid logical ID here (smallest logical id is 7)
    assert gapped_venues_loader.locate_venue(1, per_page=50) is None


def test_load_venue_members_resolves_logical_id(gapped_venues_loader):
    result = gapped_venues_loader.load_venue_members(10, page=1, per_page=50, subset_filter=None)
    assert result['venue_name'] == 'Pub'
    assert len(result['subsets']) == 1
    member_ids = {member['id'] for member in result['subsets'][0]['members']}
    assert member_ids == {0, 1}

    # School (25) has no subsets
    empty = gapped_venues_loader.load_venue_members(25, page=1, per_page=50, subset_filter=None)
    assert empty['subsets'] == []


def test_load_unit_venues_returns_logical_ids(gapped_venues_loader):
    london = gapped_venues_loader.load_unit_venues('London', page=1, per_page=50, type_filter=None)
    assert {venue['id'] for venue in london['venues']} == {10, 25}  # Camden is London's subtree

    camden = gapped_venues_loader.load_unit_venues('Camden', page=1, per_page=50, type_filter=None)
    assert [venue['id'] for venue in camden['venues']] == [25]

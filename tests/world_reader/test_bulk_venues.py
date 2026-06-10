"""Tests for RecordReader.load_venues_by_type (bulk venue read for the map layer)."""

import numpy as np
import pytest
import h5py

from world_reader import RecordReader, build_world_store


@pytest.fixture
def bulk_venues_h5(tmp_path):
    """Minimal world with 5 venues across 2 types ('bar', 'education').

    venue 0 'Pub'     bar,       coords, 1 subset  (regulars: 3)            -> num_members 3
    venue 1 'Club'    bar,       coords, 2 subsets (staff: 2, members: 5)   -> num_members 7
    venue 2 'Vault'   bar,       no coords, no subsets                      -> excluded (NaN)
    venue 3 'School'  education, coords, no subsets                         -> num_members 0
    venue 4 'College' education, no coords, no subsets                      -> excluded (NaN)
    """
    h5_path = tmp_path / 'bulk_venues.h5'
    dt = h5py.string_dtype()
    with h5py.File(h5_path, 'w') as f:
        # geography: single unit 'London'
        f.create_dataset('geography/ids',         data=np.array([0], dtype=np.int32))
        f.create_dataset('geography/parent_ids',  data=np.array([-1], dtype=np.int32))
        f.create_dataset('geography/levels',      data=np.array([0], dtype=np.int32))
        f.create_dataset('metadata/names/geography',
                         data=np.array([b'London'], dtype=dt))
        f.create_dataset('metadata/registries/geo_levels',
                         data=np.array([b'city'], dtype=dt))

        # population: 3 people in London
        f.create_dataset('population/ids',          data=np.array([0, 1, 2], dtype=np.int32))
        f.create_dataset('population/ages',         data=np.array([30, 40, 5], dtype=np.int32))
        f.create_dataset('population/sexes',        data=np.array([0, 1, 0], dtype=np.uint8))
        f.create_dataset('population/geo_unit_ids', data=np.array([0, 0, 0], dtype=np.int32))

        # venues: 0,1,2 'bar' (type 0); 3,4 'education' (type 1)
        f.create_dataset('venues/ids',          data=np.arange(5, dtype=np.int32))
        f.create_dataset('venues/geo_unit_ids', data=np.array([0, 0, 0, 0, 0], dtype=np.int32))
        f.create_dataset('venues/types',        data=np.array([0, 0, 0, 1, 1], dtype=np.uint8))
        f.create_dataset('venues/latitudes',
                         data=np.array([51.5, 51.6, np.nan, 51.7, np.nan], dtype=np.float32))
        f.create_dataset('venues/longitudes',
                         data=np.array([-0.1, -0.2, np.nan, -0.3, np.nan], dtype=np.float32))
        f.create_dataset('metadata/names/venues',
                         data=np.array([b'Pub', b'Club', b'Vault', b'School', b'College'], dtype=dt))
        f.create_dataset('metadata/registries/venue_types',
                         data=np.array([b'bar', b'education'], dtype=dt))

        # subsets: venue 0 has 1, venue 1 has 2, venues 2-4 have none
        f.create_dataset('venues/subsets/venue_ids',     data=np.array([0, 1, 1], dtype=np.int32))
        f.create_dataset('venues/subsets/member_counts', data=np.array([3, 2, 5], dtype=np.int32))
        f.create_dataset('metadata/names/subsets',
                         data=np.array([b'regulars', b'staff', b'members'], dtype=dt))
    return h5_path


@pytest.fixture
def bulk_venues_loader(bulk_venues_h5):
    world = build_world_store(str(bulk_venues_h5))
    return RecordReader(str(bulk_venues_h5), world)


def test_load_venues_by_type_returns_expected_rows(bulk_venues_loader):
    bars = bulk_venues_loader.load_venues_by_type('bar')
    assert {venue['id'] for venue in bars} == {0, 1}  # venue 2 skipped (no coordinates)

    pub = next(venue for venue in bars if venue['id'] == 0)
    assert pub['name'] == 'Pub'
    assert pub['type'] == 'bar'
    assert pub['geo_unit'] == 'London'
    assert pub['coordinates'] == [pytest.approx(51.5), pytest.approx(-0.1)]
    assert pub['num_members'] == 3
    assert pub['properties'] == {}

    club = next(venue for venue in bars if venue['id'] == 1)
    assert club['num_members'] == 7  # summed across two subsets (2 + 5)


def test_load_venues_by_type_handles_no_subsets_and_skips_nan_coordinates(bulk_venues_loader):
    schools = bulk_venues_loader.load_venues_by_type('education')
    assert len(schools) == 1
    school = schools[0]
    assert school['id'] == 3
    assert school['name'] == 'School'
    assert school['num_members'] == 0  # no subsets


def test_load_venues_by_type_unknown_type_returns_empty(bulk_venues_loader):
    assert bulk_venues_loader.load_venues_by_type('unknown') == []

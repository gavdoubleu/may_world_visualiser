"""Locks RecordReader's construction contract: (hdf5_path, store)."""

import h5py

from world_map.testing import WorldBuilder
from world_reader import RecordReader
from world_reader.statistics import compute_geographical_distribution


def test_record_reader_constructed_from_hdf5_path_and_store():
    world  = WorldBuilder().add_unit('Norfolk', population=3).build_world()
    reader = RecordReader(world._builder_hdf5_path, world)

    result = reader.load_unit_people('Norfolk', page=1, per_page=50)

    assert result['total_count'] == 3
    assert len(result['people']) == 3


def test_compute_geographical_distribution_matches_raw_recomputation():
    """Guards the launch-time cache against staleness: the cached
    geographical_distribution on WorldStore must equal what a fresh
    bincount over the raw population/geo_unit_ids produces."""
    world  = (WorldBuilder()
              .add_unit('Norfolk', population=3)
              .add_unit('Suffolk', population=2)
              .build_world())
    reader = RecordReader(world._builder_hdf5_path, world)

    with h5py.File(world._builder_hdf5_path, 'r') as f:
        raw_geo_unit_ids = f['population/geo_unit_ids'][:]
    expected = compute_geographical_distribution(raw_geo_unit_ids, world.geography)

    assert reader.compute_geographical_distribution() == expected

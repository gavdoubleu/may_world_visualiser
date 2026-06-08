"""Locks RecordReader's construction contract: (hdf5_path, store)."""

from world_map.testing import WorldBuilder
from world_reader import RecordReader


def test_record_reader_constructed_from_hdf5_path_and_store():
    world  = WorldBuilder().add_unit('Norfolk', population=3).build_world()
    reader = RecordReader(world._builder_hdf5_path, world)

    result = reader.load_unit_people('Norfolk', page=1, per_page=50)

    assert result['total_count'] == 3
    assert len(result['people']) == 3

"""Tests for the world_reader package."""

import h5py
import numpy as np
import pytest

import world_reader
from world_reader import compute_unit_statistics


def test_load_geography_importable():
    assert callable(world_reader.load_geography)


@pytest.fixture
def unit_statistics_h5(tmp_path):
    """Minimal world: parent 'London' (geo_id 0) -> child 'Camden' (geo_id 1).

    People: 0, 1 in London; 2 in Camden.
    Activities: persons 0 and 1 do 'shopping' (idx 0); person 2 does 'school' (idx 1).
    """
    h5_path = tmp_path / 'unit_statistics.h5'
    dt = h5py.string_dtype()
    with h5py.File(h5_path, 'w') as f:
        f.create_dataset('geography/ids',        data=np.array([0, 1], dtype=np.int32))
        f.create_dataset('geography/parent_ids', data=np.array([-1, 0], dtype=np.int32))
        f.create_dataset('geography/levels',     data=np.array([0, 1], dtype=np.int32))
        f.create_dataset('metadata/names/geography',
                         data=np.array([b'London', b'Camden'], dtype=dt))
        f.create_dataset('metadata/registries/geo_levels',
                         data=np.array([b'city', b'borough'], dtype=dt))

        f.create_dataset('population/ids',          data=np.array([0, 1, 2], dtype=np.int32))
        f.create_dataset('population/ages',         data=np.array([30, 40, 5], dtype=np.int32))
        f.create_dataset('population/sexes',        data=np.array([0, 1, 0], dtype=np.uint8))
        f.create_dataset('population/geo_unit_ids', data=np.array([0, 0, 1], dtype=np.int32))

        f.create_dataset('activity_mappings/activity_map/activity_data',
                         data=np.array([[0, 0], [1, 0], [2, 1]], dtype=np.int64))
        f.create_dataset('activity_mappings/activity_map/activity_names',
                         data=np.array([b'shopping', b'school'], dtype=dt))
    return h5_path


def _load_geography_from(h5_path):
    with h5py.File(h5_path, 'r') as f:
        geo_names      = f['metadata']['names']['geography'][:].astype(str)
        level_registry = f['metadata']['registries']['geo_levels'][:].astype(str)
        return world_reader.load_geography(f['geography'], geo_names, level_registry)


def test_compute_unit_statistics_omits_activity_counts_when_disabled(unit_statistics_h5):
    with h5py.File(unit_statistics_h5, 'r') as f:
        geography = _load_geography_from(unit_statistics_h5)
        stats = compute_unit_statistics(f, geography, include_activity_counts=False)

    assert stats['London'].activity_counts == {}
    assert stats['Camden'].activity_counts == {}
    assert stats['London'].population == 3  # aggregated: 2 in London + 1 in Camden
    assert stats['Camden'].population == 1


def test_compute_unit_statistics_aggregates_activity_counts_when_enabled(unit_statistics_h5):
    with h5py.File(unit_statistics_h5, 'r') as f:
        geography = _load_geography_from(unit_statistics_h5)
        stats = compute_unit_statistics(f, geography, include_activity_counts=True)

    assert stats['Camden'].activity_counts == {'school': 1}
    assert stats['London'].activity_counts == {'shopping': 2, 'school': 1}

"""Tests for the compute_activity_stats gate on load_world_from_hdf5.

Live WorldMap loads with the fast default (no activity-stats np.unique);
the static export loads with compute_activity_stats=True so it keeps
showing activity stats. See docs/handoff/activity-stats-on-demand.md.
"""

import h5py
import numpy as np
import pytest

from world_map.core.world_loader import load_world_from_hdf5


@pytest.fixture
def activity_world_h5(tmp_path):
    """Minimal world: parent 'London' (geo_id 0) -> child 'Camden' (geo_id 1).

    People: 0, 1 in London; 2 in Camden.
    Activities: persons 0 and 1 do 'shopping' (idx 0); person 2 does 'school' (idx 1).
    """
    h5_path = tmp_path / 'activity_world.h5'
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
        f.create_dataset('activity_mappings/activity_map/activity_offsets',
                         data=np.array([0, 1, 2], dtype=np.int64))
    return h5_path


def test_fast_load_omits_activity_stats(activity_world_h5):
    world = load_world_from_hdf5(str(activity_world_h5))

    assert 'activity_map' not in world._slim_statistics
    assert world._unit_statistics['London'].activity_counts == {}
    assert world._unit_statistics['Camden'].activity_counts == {}


def test_export_load_keeps_activity_stats(activity_world_h5):
    world = load_world_from_hdf5(str(activity_world_h5), compute_activity_stats=True)

    assert world._slim_statistics['activity_map']['activity_counts'] == {
        'shopping': 2, 'school': 1,
    }
    assert world._unit_statistics['Camden'].activity_counts == {'school': 1}
    assert world._unit_statistics['London'].activity_counts == {'shopping': 2, 'school': 1}

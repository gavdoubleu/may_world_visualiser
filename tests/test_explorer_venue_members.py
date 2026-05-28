"""TDD test for get_venue_members: person IDs in members_flat must be converted
to array indices before indexing population datasets."""

import numpy as np
import pytest
import h5py
from flask import Flask

from world_map.context import _CTX_KEY
from world_map.testing import WorldBuilder
from world_explorer.context import ExplorerContext, _EXPLORER_CTX_KEY
from world_explorer.explorer_loader import ExplorerLoader
from world_explorer.routes.explorer import explorer_bp


@pytest.fixture
def venue_members_h5(tmp_path):
    """Minimal HDF5 where person IDs != array positions.

    Population array order: [id=2, id=0, id=1] (sorted by geo_unit in serialiser).
    Venue 0 has one subset 'residents' with members_flat=[0, 2] (person IDs).

    Correct lookup:
      person ID 0 → array index 1 → age=35, sex=female, geo_unit=200
      person ID 2 → array index 0 → age=25, sex=male,   geo_unit=100
    """
    h5_path = tmp_path / 'test_world.h5'
    with h5py.File(h5_path, 'w') as f:
        f.create_dataset('population/ids',          data=np.array([2, 0, 1], dtype=np.int32))
        f.create_dataset('population/ages',         data=np.array([25, 35, 45], dtype=np.int32))
        f.create_dataset('population/sexes',        data=np.array([0, 1, 0], dtype=np.int8))
        f.create_dataset('population/geo_unit_ids', data=np.array([100, 200, 100], dtype=np.int32))

        f.create_dataset('venues/subsets/venue_ids',       data=np.array([0], dtype=np.int32))
        f.create_dataset('venues/subsets/members_offsets', data=np.array([0, 2], dtype=np.int64))
        f.create_dataset('venues/subsets/members_flat',    data=np.array([0, 2], dtype=np.int32))

        dt = h5py.string_dtype()
        f.create_dataset('metadata/names/venues',  data=np.array([b'test_venue'], dtype=dt))
        f.create_dataset('metadata/names/subsets', data=np.array([b'residents'], dtype=dt))
    return h5_path


@pytest.fixture
def explorer_client(venue_members_h5):
    """Flask test client with explorer_bp and ExplorerContext set up."""
    # PERSON_ID_TO_IDX: id0→idx1, id1→idx2, id2→idx0
    person_id_to_idx  = np.array([1, 2, 0], dtype=np.int64)
    subset_venue_ids  = np.array([0], dtype=np.int64)
    world             = WorldBuilder().build_world()
    loader            = ExplorerLoader(venue_members_h5, person_id_to_idx, subset_venue_ids,
                                       world.geography)

    app = Flask(__name__)
    app.config['TESTING']         = True
    app.config[_CTX_KEY]          = WorldBuilder().build_context()
    app.config[_EXPLORER_CTX_KEY] = ExplorerContext(
        world=world,
        venue_index={},
        explorer_loader=loader,
    )
    app.register_blueprint(explorer_bp)
    return app.test_client()


def test_venue_members_ids_and_geo_units_are_correct(explorer_client):
    resp = explorer_client.get('/api/explorer/venue/0/members')
    assert resp.status_code == 200
    data = resp.get_json()

    assert data['venue_id'] == 0
    assert len(data['subsets']) == 1
    subset = data['subsets'][0]
    assert subset['name'] == 'residents'
    assert subset['total'] == 2

    members = subset['members']
    assert len(members) == 2

    by_id = {m['id']: m for m in members}

    assert 0 in by_id, f"person ID 0 missing; got IDs {list(by_id)}"
    assert 2 in by_id, f"person ID 2 missing; got IDs {list(by_id)}"

    m0 = by_id[0]
    assert m0['age'] == 35,         f"person 0: expected age 35, got {m0['age']}"
    assert m0['sex'] == 'female',   f"person 0: expected female, got {m0['sex']}"
    assert m0['geo_unit'] == '200', f"person 0: expected geo_unit '200', got {m0['geo_unit']}"

    m2 = by_id[2]
    assert m2['age'] == 25,         f"person 2: expected age 25, got {m2['age']}"
    assert m2['sex'] == 'male',     f"person 2: expected male, got {m2['sex']}"
    assert m2['geo_unit'] == '100', f"person 2: expected geo_unit '100', got {m2['geo_unit']}"

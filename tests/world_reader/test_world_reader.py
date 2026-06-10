"""Tests for the world_reader package."""

import h5py
import numpy as np
import pytest

import world_reader
from world_reader import compute_unit_statistics
from world_reader.statistics import compute_venue_type_counts


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


@pytest.fixture
def venue_only_unit_h5(tmp_path):
    """England (0) -> Westfield (1) -> Stratford (2).

    Population lives entirely in Stratford (the leaf); Westfield is non-leaf
    (has a child) yet has venues directly assigned to it and zero direct
    residents — mirrors the real-world 'E02004303' shape that
    compute_unit_statistics silently dropped (population-gated leaf_stats).
    """
    h5_path = tmp_path / 'venue_only_unit.h5'
    dt = h5py.string_dtype()
    with h5py.File(h5_path, 'w') as f:
        f.create_dataset('geography/ids',        data=np.array([0, 1, 2], dtype=np.int32))
        f.create_dataset('geography/parent_ids', data=np.array([-1, 0, 1], dtype=np.int32))
        f.create_dataset('geography/levels',     data=np.array([0, 1, 2], dtype=np.int32))
        f.create_dataset('metadata/names/geography',
                         data=np.array([b'England', b'Westfield', b'Stratford'], dtype=dt))
        f.create_dataset('metadata/registries/geo_levels',
                         data=np.array([b'country', b'borough', b'ward'], dtype=dt))

        # population: both residents in Stratford (2); Westfield has none directly
        f.create_dataset('population/ids',          data=np.array([0, 1], dtype=np.int32))
        f.create_dataset('population/ages',         data=np.array([30, 40], dtype=np.int32))
        f.create_dataset('population/sexes',        data=np.array([0, 1], dtype=np.uint8))
        f.create_dataset('population/geo_unit_ids', data=np.array([2, 2], dtype=np.int32))

        # venues: both directly assigned to Westfield (1), the population-less non-leaf
        f.create_dataset('venues/ids',          data=np.array([0, 1], dtype=np.int32))
        f.create_dataset('venues/geo_unit_ids', data=np.array([1, 1], dtype=np.int32))
        f.create_dataset('venues/types',        data=np.array([0, 1], dtype=np.uint8))
        f.create_dataset('metadata/names/venues',
                         data=np.array([b'Cineplex', b'Acme Office'], dtype=dt))
        f.create_dataset('metadata/registries/venue_types',
                         data=np.array([b'cinema', b'office'], dtype=dt))
    return h5_path


@pytest.fixture
def parent_child_venue_unit_h5(tmp_path):
    """England (0) -> Westfield (1), with a ParentVenue/ChildVenue pair both
    directly assigned to Westfield: 'Acme Corp' (company, parent_id -1) and
    'Acme Office' (office, parent_id 0 — child of Acme Corp).

    ChildVenues never appear in a unit's top-level venue list (CONTEXT.md);
    compute_unit_statistics's per-type counts must agree — only the parent's
    type ('company') should be counted, not the child's ('office')."""
    h5_path = tmp_path / 'parent_child_venue_unit.h5'
    dt = h5py.string_dtype()
    with h5py.File(h5_path, 'w') as f:
        f.create_dataset('geography/ids',        data=np.array([0, 1], dtype=np.int32))
        f.create_dataset('geography/parent_ids', data=np.array([-1, 0], dtype=np.int32))
        f.create_dataset('geography/levels',     data=np.array([0, 1], dtype=np.int32))
        f.create_dataset('metadata/names/geography',
                         data=np.array([b'England', b'Westfield'], dtype=dt))
        f.create_dataset('metadata/registries/geo_levels',
                         data=np.array([b'country', b'borough'], dtype=dt))

        f.create_dataset('population/ids',          data=np.array([0], dtype=np.int32))
        f.create_dataset('population/ages',         data=np.array([30], dtype=np.int32))
        f.create_dataset('population/sexes',        data=np.array([0], dtype=np.uint8))
        f.create_dataset('population/geo_unit_ids', data=np.array([1], dtype=np.int32))

        f.create_dataset('venues/ids',          data=np.array([0, 1], dtype=np.int32))
        f.create_dataset('venues/geo_unit_ids', data=np.array([1, 1], dtype=np.int32))
        f.create_dataset('venues/types',        data=np.array([0, 1], dtype=np.uint8))
        f.create_dataset('venues/parent_ids',   data=np.array([-1, 0], dtype=np.int32))
        f.create_dataset('metadata/names/venues',
                         data=np.array([b'Acme Corp', b'Acme Office'], dtype=dt))
        f.create_dataset('metadata/registries/venue_types',
                         data=np.array([b'company', b'office'], dtype=dt))
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

    london_id = geography.get_unit('London').id
    camden_id = geography.get_unit('Camden').id
    assert stats[london_id].activity_counts == {}
    assert stats[camden_id].activity_counts == {}
    assert stats[london_id].population == 3  # aggregated: 2 in London + 1 in Camden
    assert stats[camden_id].population == 1


def test_compute_unit_statistics_aggregates_activity_counts_when_enabled(unit_statistics_h5):
    with h5py.File(unit_statistics_h5, 'r') as f:
        geography = _load_geography_from(unit_statistics_h5)
        stats = compute_unit_statistics(f, geography, include_activity_counts=True)

    london_id = geography.get_unit('London').id
    camden_id = geography.get_unit('Camden').id
    assert stats[camden_id].activity_counts == {'school': 1}
    assert stats[london_id].activity_counts == {'shopping': 2, 'school': 1}


def test_compute_unit_statistics_keeps_venue_types_for_population_less_unit(venue_only_unit_h5):
    """Regression: Westfield has direct venues but zero direct residents (its
    population lives in child Stratford) — venue_types must not be dropped,
    and must surface upward to the England ancestor too."""
    with h5py.File(venue_only_unit_h5, 'r') as f:
        geography = _load_geography_from(venue_only_unit_h5)
        stats = compute_unit_statistics(f, geography, include_activity_counts=False)

    england_id   = geography.get_unit('England').id
    westfield_id = geography.get_unit('Westfield').id
    assert stats[westfield_id].venue_types == {'cinema': 1, 'office': 1}
    assert stats[westfield_id].population == 2  # aggregated up from Stratford
    assert stats[england_id].venue_types == {'cinema': 1, 'office': 1}
    assert stats[england_id].population == 2


def test_root_unit_venue_types_matches_world_level_counts(venue_only_unit_h5):
    """Cross-check: the root unit's aggregated venue_types (built up from
    per-unit direct assignments via compute_unit_statistics) must match the
    world-level totals from compute_venue_type_counts (the known-correct
    direct read of venues/types) — confirms the fix neither drops nor
    double-counts venues when folding direct assignments up to the root."""
    with h5py.File(venue_only_unit_h5, 'r') as f:
        geography        = _load_geography_from(venue_only_unit_h5)
        stats            = compute_unit_statistics(f, geography, include_activity_counts=False)
        venue_types_arr  = f['venues']['types'][:]
        venue_type_names = f['metadata']['registries']['venue_types'][:].astype(str)

    england_id = geography.get_unit('England').id
    assert stats[england_id].venue_types == compute_venue_type_counts(venue_types_arr, venue_type_names)


def test_compute_unit_statistics_excludes_child_venues_from_type_counts(parent_child_venue_unit_h5):
    """ChildVenues never appear in a unit's top-level venue list — their type
    must not be counted in venue_types either, or WorldExplorer renders an
    unreachable section that spins on 'Loading…' forever."""
    with h5py.File(parent_child_venue_unit_h5, 'r') as f:
        geography = _load_geography_from(parent_child_venue_unit_h5)
        stats = compute_unit_statistics(f, geography, include_activity_counts=False)

    england_id   = geography.get_unit('England').id
    westfield_id = geography.get_unit('Westfield').id
    assert stats[westfield_id].venue_types == {'company': 1}
    assert stats[england_id].venue_types == {'company': 1}

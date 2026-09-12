"""Unit tests for the shared ragged-HDF5-read primitives."""

import h5py
import numpy as np
import pytest

from world_reader.ragged_hdf5 import (
    bounds_for_sorted_key,
    dedup_with_inverse,
    ragged_bounds,
    read_ids_preserving_order,
)


@pytest.fixture
def in_memory_dataset():
    """A small h5py dataset enforcing the real strictly-increasing,
    non-duplicate fancy-index constraint that these primitives work around.
    """
    with h5py.File('memory.h5', mode='w', driver='core', backing_store=False) as f:
        yield f.create_dataset('values', data=np.array([10, 20, 30, 40, 50]))


def test_ragged_bounds_middle_index_uses_next_offset():
    offsets = np.array([0, 3, 5, 9])
    assert ragged_bounds(offsets, 1, flat_len=20) == (3, 5)


def test_ragged_bounds_last_index_falls_back_to_flat_len():
    offsets = np.array([0, 3, 5, 9])
    assert ragged_bounds(offsets, 3, flat_len=12) == (9, 12)


def test_ragged_bounds_empty_range_when_consecutive_offsets_equal():
    offsets = np.array([0, 3, 3, 9])
    assert ragged_bounds(offsets, 1, flat_len=12) == (3, 3)


def test_bounds_for_sorted_key_scalar_key_present():
    sorted_fk = np.array([1, 1, 1, 4, 4, 7])
    assert bounds_for_sorted_key(sorted_fk, 4) == (3, 5)


def test_bounds_for_sorted_key_scalar_key_absent_gives_empty_range():
    sorted_fk = np.array([1, 1, 1, 4, 4, 7])
    first, last = bounds_for_sorted_key(sorted_fk, 5)
    assert first == last


def test_bounds_for_sorted_key_vectorised_keys_with_duplicates():
    sorted_fk = np.array([1, 1, 1, 4, 4, 7])
    keys = np.array([4, 4, 1])
    first, last = bounds_for_sorted_key(sorted_fk, keys)
    np.testing.assert_array_equal(first, [3, 3, 0])
    np.testing.assert_array_equal(last, [5, 5, 3])


def test_read_ids_preserving_order_restores_reverse_order(in_memory_dataset):
    result = read_ids_preserving_order(in_memory_dataset, np.array([4, 1, 3]))
    np.testing.assert_array_equal(result, [50, 20, 40])


def test_read_ids_preserving_order_dedups_repeated_ids(in_memory_dataset):
    result = read_ids_preserving_order(in_memory_dataset, np.array([3, 1, 3, 0]))
    np.testing.assert_array_equal(result, [40, 20, 40, 10])


def test_read_ids_preserving_order_handles_already_sorted_unique_ids(in_memory_dataset):
    result = read_ids_preserving_order(in_memory_dataset, np.array([0, 1, 2]))
    np.testing.assert_array_equal(result, [10, 20, 30])


def test_read_ids_preserving_order_empty_ids(in_memory_dataset):
    result = read_ids_preserving_order(in_memory_dataset, np.array([], dtype=np.int64))
    assert len(result) == 0


def test_dedup_with_inverse_reused_across_datasets_matches_independent_reads(in_memory_dataset):
    other_dataset = in_memory_dataset.file.create_dataset(
        'other', data=np.array([100, 200, 300, 400, 500]))
    ids = np.array([4, 1, 4, 2])

    unique_ids, inverse = dedup_with_inverse(ids)
    values_shared = in_memory_dataset[unique_ids.tolist()][inverse]
    other_shared = other_dataset[unique_ids.tolist()][inverse]

    np.testing.assert_array_equal(values_shared, read_ids_preserving_order(in_memory_dataset, ids))
    np.testing.assert_array_equal(other_shared, read_ids_preserving_order(other_dataset, ids))

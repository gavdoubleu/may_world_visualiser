"""Shared primitives for reading ragged (variable-length-per-record) data out
of flat HDF5 datasets. App-agnostic.

Three related-but-distinct pieces of non-obvious indexing logic, each with
its own precondition — do not merge them despite superficial similarity:

- `ragged_bounds`: offsets-array boundary math (monotonic offsets indexed by
  position).
- `bounds_for_sorted_key`: binary-search bounds on a sorted-but-not-offsets
  foreign-key column.
- `read_ids_preserving_order`/`dedup_with_inverse`: h5py's fancy-indexing
  requires strictly increasing, non-duplicate index order; these restore the
  caller's original order after a dedup+sort round-trip.
"""

import numpy as np


def ragged_bounds(offsets: np.ndarray, index: int, flat_len: int) -> tuple[int, int]:
    """Boundary of one record's slice in a flat array, given a CSR-style offsets array.

    Args:
        offsets: Monotonic start-offset for each record, indexed by position.
        index: Position of the record whose bounds are wanted.
        flat_len: Total length of the flat array `offsets` indexes into —
            used as the end bound for the last record, since there is no
            `offsets[index + 1]` to read.

    Returns:
        (start, end) bounding the record's slice in the flat array.
    """
    start = int(offsets[index])
    end = int(offsets[index + 1]) if index + 1 < len(offsets) else int(flat_len)
    return start, end


def bounds_for_sorted_key(
    sorted_fk_array: np.ndarray,
    keys: int | np.ndarray,
    side_pair: tuple[str, str] = ('left', 'right'),
) -> tuple:
    """Find where a key's contiguous block starts/ends in a sorted foreign-key column.

    Binary-searches `sorted_fk_array` twice via `np.searchsorted`. `keys` may
    be scalar or an array — `np.searchsorted` handles both natively, so this
    covers both a single lookup and a vectorised lookup over many keys.

    Args:
        sorted_fk_array: A sorted (but not necessarily an offsets array)
            foreign-key column to search.
        keys: The key (or array of keys) whose contiguous block is wanted.
        side_pair: `searchsorted` sides for (first, last); the default gives
            the half-open `[first, last)` block for each key.

    Returns:
        (first, last) — scalars if `keys` is scalar, arrays if `keys` is an
        array. `first == last` means the key is absent.
    """
    first = np.searchsorted(sorted_fk_array, keys, side=side_pair[0])
    last = np.searchsorted(sorted_fk_array, keys, side=side_pair[1])
    return first, last


def dedup_with_inverse(ids: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Sort and dedup `ids`, plus the inverse index to scatter results back to `ids`' order.

    h5py's fancy indexing requires strictly increasing, non-duplicate index
    order; `unique_ids` satisfies that. Factored out of
    `read_ids_preserving_order` so several datasets sharing one `ids`
    ordering (e.g. several parallel columns for the same rows) can reuse a
    single dedup/sort instead of repeating it per dataset.

    Args:
        ids: The ids in the caller's original order (may repeat, need not be
            sorted).

    Returns:
        (unique_ids, inverse) — `unique_ids` is sorted and duplicate-free;
        `values[inverse]`, for `values = dataset[unique_ids.tolist()]`,
        restores `ids`' original order.
    """
    return np.unique(ids, return_inverse=True)


def read_ids_preserving_order(dataset, ids: np.ndarray) -> np.ndarray:
    """Read `dataset[ids]` from HDF5, returning values in `ids`' original order.

    h5py's fancy indexing requires strictly increasing, non-duplicate index
    order. This always dedups (via `dedup_with_inverse`) rather than a plain
    argsort/unsort — a caller whose ids happen to already be unique pays only
    the cost of `np.unique` on a small array, and no future caller can
    reintroduce the bug of using the non-dedup version where duplicates are
    actually possible.

    Args:
        dataset: An h5py dataset (or any object supporting the same
            fancy-indexing-by-list interface) to read from.
        ids: The ids to read, in the caller's desired output order (may
            repeat, need not be sorted).

    Returns:
        Values from `dataset`, in `ids`' original order.
    """
    unique_ids, inverse = dedup_with_inverse(ids)
    return dataset[unique_ids.tolist()][inverse]

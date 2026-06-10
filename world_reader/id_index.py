"""Gap-safe logical-ID -> row-index lookup.

Replaces the `arr[ids] = arange(N)` dense-array trick, which assumes IDs are
a bounded permutation of [0, N) and raises IndexError on any ID >= N — a real
case for "subset of a larger world" HDF5 files where logical IDs reference a
larger parent world and can have true gaps."""

import numpy as np


class IdIndex:
    """Looks up HDF5 row indices from logical IDs via sorted-ID binary search.

    Tolerates arbitrary gaps and orderings in the logical-ID array (only
    requires uniqueness). O(log N) per lookup; vectorises for batches."""

    MISSING = -1

    def __init__(self, ids):
        ids = np.asarray(ids)
        sort_order = np.argsort(ids, kind='stable')
        self._sorted_ids = ids[sort_order]
        self._sorted_row_idxs = sort_order

    def __len__(self):
        return len(self._sorted_ids)

    def __getitem__(self, logical_ids: int | np.ndarray) -> int | np.ndarray:
        """Look up row index (or indices) for logical_ids.

        Args:
            logical_ids: A single logical ID or an array of them.

        Returns:
            The row index (int) for a scalar input, or an array of row
            indices for array input. `MISSING` (-1) where a logical ID is
            absent.
        """
        if len(self._sorted_ids) == 0:
            missing = np.full_like(np.asarray(logical_ids), self.MISSING)
            return missing if np.ndim(logical_ids) else int(self.MISSING)
        positions = np.searchsorted(self._sorted_ids, logical_ids)
        clipped = np.clip(positions, 0, len(self._sorted_ids) - 1)
        found = self._sorted_ids[clipped] == logical_ids
        row_idxs = np.where(found, self._sorted_row_idxs[clipped], self.MISSING)
        return row_idxs if np.ndim(logical_ids) else int(row_idxs)

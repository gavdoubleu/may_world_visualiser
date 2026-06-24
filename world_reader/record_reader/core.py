"""On-demand HDF5 record reads, shared by WorldMap and WorldExplorer."""

from pathlib import Path
from typing import TYPE_CHECKING

import h5py

from world_reader.statistics import (
    compute_population_statistics as _compute_population_statistics,
)

from .person_reads import _PersonReads
from .venue_reads import _VenueReads

if TYPE_CHECKING:
    from world_reader.world_store import WorldStore


class RecordReader(_PersonReads, _VenueReads):
    """All per-request HDF5 reads, wired to a resident WorldStore for indices.

    Holds a path to the world file (opened fresh per read) and the lookup
    arrays/indices built once by `build_world_store`. Person/Venue/Subset
    reads (`_PersonReads`/`_VenueReads`) use these to locate HDF5 rows
    without materialising the full population/venue arrays.
    """

    def __init__(self, hdf5_path: str | Path, store: 'WorldStore'):
        """Wire a RecordReader to its HDF5 file and resident WorldStore.

        Args:
            hdf5_path: Path to world_state.h5.
            store: WorldStore built by `build_world_store` for this file.
        """
        self._hdf5_path = str(hdf5_path)
        self._person_id_to_idx    = store.person_id_to_idx
        self._subset_venue_ids    = store.subset_venue_ids
        self._venue_ids           = store.venue_ids
        self._venue_id_to_idx     = store.venue_id_to_idx
        self._geography           = store.geography
        self._subtree_index       = store.subtree_index
        self._geographical_distribution = store.geographical_distribution
        self._venue_types_arr     = store.venue_types_arr
        self._venue_type_names_cache = store.venue_type_names or []
        self._activity_names_cache   = store.activity_names or []
        self._venue_list_position = store.venue_list_position
        self._person_list_position = store.person_list_position
        self._venue_parent_ids           = store.venue_parent_ids
        self._venue_child_position       = store.venue_child_position
        self._venue_child_counts         = store.venue_child_counts
        self._venue_child_total_members  = store.venue_child_total_members
        self._children_by_parent_sorted  = store.children_by_parent_sorted
        self._children_parent_ids_sorted = store.children_parent_ids_sorted

    # ── whole-world aggregate reads ──────────────────────────────────────────

    def compute_population_statistics(self) -> dict:
        """Population-wide total/age/sex aggregates (see world_reader.statistics)."""
        with h5py.File(self._hdf5_path, 'r') as f:
            return _compute_population_statistics(f)

    def compute_geographical_distribution(self) -> dict:
        """Per-level counts of people by their direct geo unit (precomputed at launch)."""
        return self._geographical_distribution

    def get_venue_type_counts(self) -> dict:
        """Venue counts keyed by type name."""
        from world_reader.statistics import compute_venue_type_counts
        return compute_venue_type_counts(self._venue_types_arr, self._venue_type_names_cache)

    def get_venue_type_names_present(self) -> list:
        """Insertion-order list of VenueType names that have at least one venue."""
        if self._venue_types_arr is None:
            return []
        from world_reader.statistics import venue_type_names_present
        return venue_type_names_present(self._venue_types_arr, self._venue_type_names_cache)

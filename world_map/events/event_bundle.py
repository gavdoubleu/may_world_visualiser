"""Pure-data IO boundary between HDF5 loading and event aggregation."""

from __future__ import annotations
from dataclasses import dataclass
import numpy as np


@dataclass
class EventDataBundle:
    """Preprocessed event arrays ready for aggregation. Constructable in tests without HDF5."""
    events_sorted:    dict[str, np.ndarray]
    events_times:     dict[str, np.ndarray]
    venue_geo_array:  np.ndarray | None
    person_geo_array: np.ndarray | None
    n_geo:            int
    time_min:         float
    time_max:         float

"""Shared lazy HDF5 backend for WorldMap and WorldExplorer.

Re-exports the public API: numpy/HDF5 conversion helpers (`convert`), the
GeoUnit hierarchy and stats loader (`geography`), pagination helpers
(`pagination`), per-unit/world statistics (`statistics`), the resident
`WorldStore` (`world_store`), and the on-demand `RecordReader`
(`record_reader`). Neither app materialises Person/Venue/Subset objects;
only the geography tree and aggregate stats are resident. See
`docs/architecture.md` for the overall design.
"""

from world_reader.convert import (
    SEX_DECODE, decode_str, convert_numpy_value, convert_numpy_types,
)
from world_reader.geography import (
    AGE_LABELS, AGE_BREAKS, age_label,
    UnitStats, GeoUnit, GeographyManager, load_geography,
)
from world_reader.pagination import PaginationSlice, paginate, calc_total_pages
from world_reader.statistics import compute_unit_statistics
from world_reader.world_store import WorldStore, build_world_store
from world_reader.record_reader import RecordReader
from world_reader.calendar_event_reader import CalendarEventReader

__all__ = [
    'SEX_DECODE', 'decode_str', 'convert_numpy_value', 'convert_numpy_types',
    'AGE_LABELS', 'AGE_BREAKS', 'age_label',
    'UnitStats', 'GeoUnit', 'GeographyManager', 'load_geography',
    'PaginationSlice', 'paginate', 'calc_total_pages',
    'compute_unit_statistics',
    'WorldStore', 'RecordReader', 'build_world_store',
    'CalendarEventReader',
]

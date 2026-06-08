"""Numpy-to-Python conversion and HDF5 value decoding.

App-agnostic: no dependency on world_map or world_explorer. The canonical home
for the conversion helpers that were previously duplicated across
world_map.core.world_loader, world_map.utils and world_explorer.explorer_loader.
"""

import numpy as np

# Sex codes as stored in the HDF5 population group.
SEX_DECODE = {0: "male", 1: "female", 2: "unknown"}


def decode_str(value) -> str:
    """Decode an HDF5 scalar (bytes or otherwise) to a Python str."""
    return value.decode() if isinstance(value, bytes) else str(value)


def convert_numpy_value(value):
    """Convert a single numpy scalar/array (recursively) to native Python types.

    Used for HDF5 property values, which may be nested arrays or byte strings.
    """
    if value is None:
        return None
    if isinstance(value, (np.integer, np.int64, np.int32)):
        return int(value)
    if isinstance(value, (np.floating, np.float64, np.float32)):
        return float(value)
    if isinstance(value, np.ndarray):
        return [convert_numpy_value(v) for v in value]
    if isinstance(value, (np.str_, np.bytes_)):
        return str(value)
    if isinstance(value, bytes):
        return value.decode('utf-8')
    return value


def convert_numpy_types(obj) -> object:
    """Recursively convert numpy scalars/arrays in a response structure to native
    Python types, descending into dicts/lists/tuples/sets.

    Used to make API responses JSON-serialisable.
    """
    if obj is None:
        return None
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.str_):
        return str(obj)
    if isinstance(obj, dict):
        return {str(k): convert_numpy_types(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [convert_numpy_types(item) for item in obj]
    return obj

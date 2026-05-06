"""Shared utilities with no dependency on the Flask factory."""


def convert_numpy_types(obj) -> object:
    """Recursively convert numpy scalars/arrays to Python native types."""
    import numpy as np

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

"""Tests for world_map.utils."""

import numpy as np
from world_map.utils import convert_numpy_types


def test_convert_numpy_types_importable():
    assert callable(convert_numpy_types)


def test_converts_numpy_int():
    assert convert_numpy_types(np.int64(42)) == 42
    assert isinstance(convert_numpy_types(np.int64(42)), int)


def test_converts_nested_dict():
    result = convert_numpy_types({'a': np.float32(1.5), 'b': [np.int32(3)]})
    assert result == {'a': 1.5, 'b': [3]}
    assert isinstance(result['a'], float)

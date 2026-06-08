"""Tests for world_map.utils and world_reader.convert."""

import numpy as np
from world_map.utils import convert_numpy_types
from world_reader.convert import SEX_DECODE, convert_numpy_value


def test_convert_numpy_types_importable():
    assert callable(convert_numpy_types)


def test_converts_numpy_int():
    assert convert_numpy_types(np.int64(42)) == 42
    assert isinstance(convert_numpy_types(np.int64(42)), int)


def test_converts_nested_dict():
    result = convert_numpy_types({'a': np.float32(1.5), 'b': [np.int32(3)]})
    assert result == {'a': 1.5, 'b': [3]}
    assert isinstance(result['a'], float)


def test_convert_numpy_value_decodes_bytes():
    assert convert_numpy_value(b'leeds') == 'leeds'


def test_convert_numpy_value_recurses_arrays():
    result = convert_numpy_value(np.array([np.int32(1), np.int32(2)]))
    assert result == [1, 2]
    assert all(isinstance(item, int) for item in result)


def test_sex_decode_maps_codes():
    assert SEX_DECODE == {0: 'male', 1: 'female', 2: 'unknown'}

"""Smoke test for the world_reader package."""

import world_reader


def test_load_geography_importable():
    assert callable(world_reader.load_geography)

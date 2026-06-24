"""Regression test for the astype(str) fixed-width OOM in _compute_array_stats."""

import time

import numpy as np

from world_reader.statistics import _compute_array_stats


def test_categorical_stats_survive_single_huge_outlier_string():
    rng = np.random.default_rng(0)
    short_strings = rng.choice(['alice', 'bob', 'carol', 'dave'], size=100_000)
    data = np.array(short_strings.tolist() + ['x' * 500_000], dtype=object)

    start = time.monotonic()
    result = _compute_array_stats(data)
    elapsed = time.monotonic() - start

    assert result['type'] == 'categorical'
    assert result['count'] == 100_001
    assert result['unique_count'] == 5
    assert elapsed < 5.0

"""Tests for world_map.core.pagination."""

import pytest
from world_map.core.pagination import PaginationSlice, calc_total_pages, paginate


def test_paginate_normal():
    items = list(range(10))
    sl = paginate(items, page=2, per_page=3)
    assert sl.items == [3, 4, 5]
    assert sl.total == 10
    assert sl.total_pages == 4
    assert sl.page == 2
    assert sl.per_page == 3


def test_paginate_first_page():
    items = list(range(5))
    sl = paginate(items, page=1, per_page=3)
    assert sl.items == [0, 1, 2]
    assert sl.total == 5
    assert sl.total_pages == 2


def test_paginate_last_page_partial():
    items = list(range(7))
    sl = paginate(items, page=3, per_page=3)
    assert sl.items == [6]
    assert sl.total_pages == 3


def test_paginate_page_beyond_end():
    items = list(range(5))
    sl = paginate(items, page=99, per_page=10)
    assert sl.items == []
    assert sl.total == 5


def test_paginate_empty_list():
    sl = paginate([], page=1, per_page=50)
    assert sl.items == []
    assert sl.total == 0
    assert sl.total_pages == 1


def test_calc_total_pages_zero_items():
    assert calc_total_pages(0, 50) == 1


def test_calc_total_pages_exact_multiple():
    assert calc_total_pages(100, 10) == 10


def test_calc_total_pages_remainder():
    assert calc_total_pages(101, 10) == 11

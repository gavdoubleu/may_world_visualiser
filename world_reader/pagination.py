"""Shared pagination utility for list-based route handlers. App-agnostic.

Convention: `paginate`/`PaginationSlice` are for routes (and tests) that hold
a fully materialised Python list. `RecordReader` (record_reader/core.py) instead
hand-slices numpy arrays/HDF5 datasets and only reuses `calc_total_pages` —
wrapping its results in `paginate` would force materialising full arrays just
to re-slice them, defeating its lazy-read design. Both patterns are
intentional; do not "unify" them onto one shape.
"""

from dataclasses import dataclass


@dataclass
class PaginationSlice:
    items: list
    total: int
    total_pages: int
    page: int
    per_page: int


def paginate(items: list, page: int, per_page: int) -> PaginationSlice:
    total   = len(items)
    n_pages = calc_total_pages(total, per_page)
    start   = (page - 1) * per_page
    return PaginationSlice(items[start:start + per_page], total, n_pages, page, per_page)


def calc_total_pages(total: int, per_page: int) -> int:
    return max(1, (total + per_page - 1) // per_page)

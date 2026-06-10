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
    """One page of a fully materialised list, plus pagination metadata.

    Attributes:
        items: The items for this page.
        total: Total number of items across all pages.
        total_pages: Total number of pages.
        page: 1-indexed page number for this slice.
        per_page: Page size used to compute `total_pages` and the slice.
    """

    items: list
    total: int
    total_pages: int
    page: int
    per_page: int


def paginate(items: list, page: int, per_page: int) -> PaginationSlice:
    """Slice a fully materialised list into one page.

    Args:
        items: The full list to paginate.
        page: 1-indexed page number.
        per_page: Page size.

    Returns:
        A PaginationSlice for the requested page.
    """
    total   = len(items)
    n_pages = calc_total_pages(total, per_page)
    start   = (page - 1) * per_page
    return PaginationSlice(items[start:start + per_page], total, n_pages, page, per_page)


def calc_total_pages(total: int, per_page: int) -> int:
    """Number of pages needed to cover `total` items at `per_page` each (minimum 1)."""
    return max(1, (total + per_page - 1) // per_page)

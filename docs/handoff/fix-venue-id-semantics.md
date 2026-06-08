# Handoff — fix venue ID semantics in `world_reader`

**Found during:** grilling session for PR6 (migrate WorldMap onto the `world_reader`
lazy backend — see [`pr-06-migrate-worldmap-backend.md`](pr-06-migrate-worldmap-backend.md)).
**Status:** independent bug, not yet started. Can land before, alongside, or as
part of PR8 (see "Where this intersects" below).

## Problem

`ExplorerLoader`'s venue methods (`load_venue_detail`, `load_venues_by_type`,
`load_unit_venues`, `load_venue_children` — `world_reader/explorer_loader.py`)
all return `'id'` as the **HDF5 array row index**, not the logical ID stored in
`venues/ids`. Internally, `subset_venue_ids`, `venue_parent_ids`,
`venue_child_counts`, `venue_child_total_members`,
`children_by_parent_sorted`/`children_parent_ids_sorted` are all row-index
aligned, and helpers (`_venue_subsets`, `_unit_name`) take row indices directly
— there is no `venue_id_to_idx` translation layer at the API boundary.

This is silently correct today only because `venues/ids == arange(N)` on
`data/world_state_medieval.h5` (verified: `ids[:10] == [0..9]`, `min == 0`,
`max == N - 1`, `np.array_equal(ids, arange(len(ids)))` → `True`). It will
silently misreport venue identity on any dataset where venue IDs are
sparse/non-contiguous — exactly the situation **persons** are already in on
this same file (`population/ids != arange(N)`).

## What's already correct (verified — don't re-derive)

- **Persons**: correct. `person_id_to_idx` is a logical-id → row-index lookup
  array built in `world_reader/explorer_world.py:260-261`
  (`person_id_to_idx[person_ids] = np.arange(len(person_ids))`).
  `ExplorerLoader` looks up `array_idx = person_id_to_idx[person_id]` to
  navigate, then reads the logical `id_val` back from `population/ids` for the
  response (`explorer_loader.py:165, 216, 241`).
- **GeoUnits**: correct. `GeoUnit.id = int(unit_id)` reads the logical value
  straight from the `geography/ids` array (`world_reader/geography.py:142`),
  never the loop index.
- **Venues**: the only broken case (see above).

## Fix shape (mirror the person pattern)

1. Build a `venue_id_to_idx` lookup array at load time in `load_explorer_world`
   (`world_reader/explorer_world.py`), the same way `person_id_to_idx` is built
   — fancy-indexed from `venues/ids`.
2. Thread it through `ExplorerWorld` and into `ExplorerLoader`.
3. At every venue API boundary (`load_venue_detail`, `load_venues_by_type`,
   `load_unit_venues`, `load_venue_children`, `locate_venue`,
   `load_venue_members`): translate incoming `venue_id` path params — which are
   **logical IDs** — to row indices via `venue_id_to_idx[venue_id]` for array
   reads, and return the logical ID (read back from `venues/ids[row]`, or echo
   the validated input) as `'id'` in the response.
4. Internal arrays (`subset_venue_ids` searchsorted, `venue_parent_ids[row]`,
   child arrays) stay row-index aligned — only the API-facing `'id'` changes.

## Where this intersects other in-flight work

- **PR6**: migrates `/api/venues/venue/<id>` from `ctx.venue_index.get(id)`
  (keyed by the logical `venue.id`) onto `ExplorerLoader.load_venue_detail`. If
  PR6 lands before this fix, it inherits the bug — silently correct on the
  current dataset, latent on others. Flag it in the PR6 PR description/handoff
  as a **known pre-existing `world_reader` issue**, not a regression introduced
  by the migration (it already affects WorldExplorer today).
- **PR8** (`pr-08-rename-deepen-seam.md`): collapses `ExplorerLoader`'s
  constructor from 16 loose args to `(hdf5_path, store)`. Adding
  `venue_id_to_idx` to `ExplorerWorld`'s resident state and reaching into
  `store` for it from the new constructor is the natural landing spot —
  consider folding this fix into PR8 rather than widening the seam twice.

## Test to add

A fixture HDF5 with **non-contiguous** `venues/ids` (mirror the synthetic-world
builders in `tests/test_explorer_loader.py` / `tests/test_bulk_venues.py`).
Assert `load_venue_detail`/`load_venues_by_type`/`load_unit_venues` return the
*logical* ID, not the row position. This is the regression guard — the bug is
invisible on contiguous-ID fixtures, which is presumably why it hasn't been
caught yet.

## Suggested skills

- `tdd` — write the non-contiguous-ID fixture test first (red), then add
  `venue_id_to_idx` and the translation layer (green).
- `git_commits` — UK English, concise; no AI attribution or plan/handoff-file
  references in commit messages (repo convention — see "Conventions for all
  PRs" in `00_REFACTOR_PLAN.md`).
- `code-review` — once the fix lands, check for other row-index leaks in
  venue-adjacent paths (`locate_venue`, `load_venue_members`).
</content>

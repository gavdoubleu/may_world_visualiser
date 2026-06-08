# ADR 0002: Unified lazy HDF5 backend

## Status
Accepted — 2026-06-08. Supersedes ADR 0001.

## Context
ADR 0001 gave WorldExplorer a bespoke lazy backend, accepting that WorldMap
would keep its eager in-memory object model (`Person`/`Venue`/`Subset` +
managers, `WorldData`, `load_world_from_hdf5`) on the premise that it
"genuinely needs all objects resident".

Inspection showed that premise was false: every WorldMap route had a direct
lazy equivalent already serving WorldExplorer (`ExplorerWorld`'s geography +
`UnitStats`, `ExplorerLoader`'s on-demand record reads), bar the venue map
layer, which only needed a bulk array read. The dominant eager cold-start cost
was not the object loops (~9.5s) but the activity-map `np.unique` passes
(~tens of seconds) — and WorldMap's landing page was the only thing forcing
that work.

## Decision
Retire the eager backend; both apps now share one lazy backend living in the
neutral `world_reader/` package (`ExplorerWorld`, `ExplorerLoader`,
`SubtreeIndex`, `load_explorer_world`, `compute_unit_statistics`). WorldMap was
migrated by: removing activity statistics from its landing/unit-detail panels
(deferred to a future on-demand endpoint), adding a bulk `load_venues_by_type`
read for the venue map layer, and rewriting `create_app`/`AppContext`/routes
onto the store + loader. Neither app materialises `Person`, `Venue` or
`Subset` as resident Python objects any more — both read individual records
from HDF5 on demand and hold only the geography tree, aggregate `UnitStats`,
and row indices resident.

## Consequences
- WorldMap cold start dropped from ~48.8s (eager) to ~4.9s (medieval) — the
  same lazy path WorldExplorer already used (~1.7s, no activity stats baked).
- The duplicated backend that ADR 0001 accepted as the price of the split is
  gone: one data path, one statistics computation, one HDF5 schema seam. A
  fix or schema change now needs applying once.
- Activity statistics are no longer shown on WorldMap's landing page; they
  move to an on-demand per-unit endpoint (see
  `docs/handoff/activity-stats-on-demand.md`). The static export continues to
  bake them so exported maps always show stats.
- The eager `Person`/`Venue`/`Subset`/managers/`WorldData`/
  `load_world_from_hdf5` classes and loaders are deleted
  (`world_map/core/world_data.py`, `world_map/core/world_loader.py`).
- A future combined live-map-and-explorer app (output 3) is now nearly free:
  it is a thin factory + routes + frontend over the same `world_reader` store
  and loader.

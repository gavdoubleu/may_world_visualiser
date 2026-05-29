# ADR 0001: WorldExplorer lazy HDF5 backend

## Status
Accepted — 2026-05-29

## Context
WorldExplorer and WorldMap originally shared one loader,
`world_map.core.world_loader.load_world_from_hdf5`. That loader eagerly builds the
full in-memory object model: every Person, Venue and Subset, plus two statistics
passes that run `np.unique` over the entire activity map (~2.6M rows on NZ 1918,
~30.7M on the medieval dataset).

WorldExplorer needs almost none of that. Profiling the cold start showed the
statistics passes dominate (~22.7s + ~25.3s on medieval); the object loops are a
secondary ~9.5s. Yet the explorer UI displays only per-unit population, age and
sex distributions, and venue-type counts. It never shows activity counts, and it
already reads individual Person/Venue/Subset detail lazily from HDF5 on demand.
So the bulk of the eager load is wasted work for this app.

WorldMap, by contrast, genuinely needs all objects resident — it renders every
GeoUnit and Venue on a map with event overlays.

## Decision
Give WorldExplorer a bespoke, lazy on-demand HDF5 backend, decoupled from
`world_map` on the data path. WorldMap keeps its eager in-memory model unchanged.

- `world_explorer/explorer_world_loader.py` (`load_explorer_world`) builds only
  the geography tree, aggregate per-unit statistics (population / age / sex /
  venue-type counts — **no** activity counts), and lightweight row indices
  (`person_id_to_idx`, `subset_venue_ids`, and a `SubtreeIndex`).
- `SubtreeIndex` is a DFS pre-order interval (Euler-tour) index: sorting
  population/venue rows by their unit's pre-order value makes each unit's whole
  subtree a contiguous slice, so per-unit People/Venue lists (which always
  include descendants) paginate in O(1) without materialising objects.
- `ExplorerLoader` serves single Person/Venue/Subset records and paginated
  unit People/Venue lists by reading HDF5 rows on demand.
- The explorer registers only its own blueprint; it no longer mounts
  `world_map`'s geography/population/venues blueprints or `AppContext`.
- Shared, app-agnostic helpers are still reused: `_load_geography`, the
  `UnitStats` dataclass, `pagination`, `themes.theme_css`.

## Consequences
- Cold start dropped from ~48.8s to ~1.7s (medieval) and ~7.3s to ~0.2s
  (NZ 1918).
- The two apps now have divergent backends: a bug fix or schema change on the
  data path may need applying in both `world_map.core.world_loader` and
  `world_explorer.explorer_world_loader`. This duplication is accepted as the
  price of the architectural split — the apps have genuinely different needs
  (resident object graph vs. on-demand records).
- Any future per-request endpoint added to the explorer must read from HDF5 via
  `ExplorerLoader`; it cannot assume `world.population` / `world.venues` exist
  (they are `None` on `ExplorerWorld`).
- If world-map cold start later matters, the lever there is the activity-map
  `np.unique` (e.g. a 1-D key encoding), not the object loops.

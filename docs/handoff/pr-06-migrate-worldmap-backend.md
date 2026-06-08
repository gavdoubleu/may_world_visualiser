# Handoff — PR6: migrate WorldMap onto the `world_reader` backend

**Part of:** the "collapse two HDF5 backends into one" refactor (full plan in the appendix below).
**Branch:** `refactor/06-migrate-worldmap-backend` off PR5's branch.
**Depends on:** PR1–PR5 merged.
**Risk:** HIGH — this is the keystone. Split into two commits/sub-PRs (6a, 6b). Names are still `ExplorerWorld`/`ExplorerLoader` (PR8 renames).

## Goal

Make WorldMap build the lazy `world_reader` backend (`ExplorerWorld` + `ExplorerLoader`) instead of the eager `WorldData`. **API responses must stay byte-compatible** — the static export and both frontends depend on the exact JSON. After this PR nothing constructs `WorldData`; PR7 deletes it.

## Contract / safety net (set up FIRST)

Before changing anything, capture golden JSON from the current (eager) WorldMap for a real `world_state.h5`:
- Drive `create_app(...).test_client()` over: `/api/map/config`, `/api/panel/config`, `/api/geography/levels`, `/api/geography/<level>`, `/api/geography/unit/<name>`, `/api/geography/unit/<name>/people`, `/api/venues/types`, `/api/venues/<type>`, `/api/venues/venue/<id>`, `/api/population/person/<id>`, `/api/world/statistics`. (Mirror `export_static._collect_data`, `export_static.py:141-245`.)
- Save responses. After migration, re-run and diff — they must match (modulo key ordering). Add this as a test where a fixture HDF5 is available.

## PR6a — factory, context, geography + single-record routes

- **`world_map/app.py:create_app`** (lines 50-142): build `ExplorerWorld` via `load_explorer_world(hdf5_path)` + an `ExplorerLoader`, instead of expecting an eager `world`. Keep map-specific assembly: `MAP_CONFIG`, projection (`projection`), `AppConfig.load`. Drop the `venue_index` built from `world.venues` (lines 72-76) — replaced by `ExplorerLoader.load_venue_detail`.
- **`world_map/context.py`** — `AppContext` (lines 18-24): replace `world: WorldData` + `venue_index` with the store + loader (e.g. `world` = `ExplorerWorld`, plus `explorer_loader`). Keep `projection`, `map_config`, `app_config`, `event_loader`, and the `geo_unit_names*` properties.
- **`world_map/routes/geography.py`**:
  - `/api/geography/<level>` (35-76) and `/api/geography/unit/<name>` (83-134) already use only `world.geography` + `world._unit_statistics` — `ExplorerWorld` provides both; verify they work unchanged.
  - `/api/geography/unit/<name>/people` (137-193): replace `unit.get_people()` + `paginate(...)` with `ctx.explorer_loader.load_unit_people(unit_name, page, per_page)`. Match the existing response keys (`unit_name,total_count,page,per_page,total_pages,people`) — adapt the loader's dict shape if needed.
- **`world_map/routes/venues.py:89`** (`/api/venues/venue/<id>`): replace `venue_index.get(id)` with `ctx.explorer_loader.load_venue_detail(id)`; reshape to the existing response.
- **`world_map/routes/population.py:43`** (`/api/population/person/<id>`): replace `world.population.get_person(id)` + activity_map build with `load_person_slim(id)` + `load_person_activities(id)`; reshape to the existing response.
- **Entry points:** `launch_world_map.py` and `export_static.py` (`export_static.py:644-653` `load_world_from_file`, `:812` `create_app(...)`) — load via the lazy path (build `ExplorerWorld` + pass `hdf5_path`). Note `export_static` still needs activity stats for the export (PR5 finding) — keep computing them at export time even though the live landing page no longer does.

## PR6b — venue map layer + aggregate stats

- **`world_map/routes/venues.py:35-86`** (`/api/venues/<type>`): replace the `world.venues.get_venues_by_type` iteration with `ctx.explorer_loader.load_venues_by_type(venue_type)` (PR4) and wrap into the GeoJSON `FeatureCollection`.
- **`world_map/routes/venues.py:15`** (`/api/venues/types`): serve from the store's venue-type registry / `_unit_statistics` instead of `world.venues.get_venue_types`.
- **`world_map/routes/venues.py:166`** (`/api/world/statistics`) and **`world_map/routes/population.py:15`** (`/api/population/statistics`): derive totals (population, venue counts, geo distribution) from `ExplorerWorld._unit_statistics` aggregates rather than the eager managers. Activity stats already removed in PR5.
- **`/api/households/statistics`** (`venues.py:140`): this reads `world.households` which is already always `None` (returns 404). Preserve the 404 behaviour or remove the dead route — note the choice.

## Tests

- `tests/conftest.py` builds `AppContext` directly — update the fixture to the new `AppContext` shape (or add a lazy-backed factory). `tests/test_geography.py`, `tests/test_pagination.py`, `tests/test_config.py` must pass (adapt fixtures, not assertions on response shape).
- Golden-JSON diff test from the "Contract" section.

## Verify end-to-end

- `python launch_world_map.py` against a real `world_state.h5`; load the map, click units, open a venue and a person, page through people. Compare to a pre-PR run.
- Measure cold start: expect a large drop (object loops gone). Record before/after in the PR description.

## Acceptance criteria

- [ ] Nothing constructs `WorldData` on the WorldMap path (`grep -rn "WorldData(" world_map export_static.py launch_world_map.py` → none, except the soon-deleted definition).
- [ ] Golden JSON matches pre-migration for all listed endpoints.
- [ ] Both apps run; static export still produces a working HTML with activity stats.
- [ ] `pytest -q` green.

## Commit & PR

- Two commits: `Migrate WorldMap factory/context/geography/single-record routes to lazy backend` (6a) and `Migrate WorldMap venue map layer + aggregate stats to lazy backend` (6b). May be one PR with two commits, or two stacked PRs.
- PR description: PR6 of the series; link the golden-JSON evidence and cold-start numbers.


---

# Appendix — Overall refactor plan (for reference)

# Refactor: collapse two HDF5 backends into one lazy backend

> This is the overall plan. Each `pr-NN-*.md` handoff in this directory implements
> one step of it and embeds a copy of this plan as an appendix.

## Context

`may_world_visualiser` produces three outputs from a `world_state.h5` file:
1. **Static HTML export** (`export_static.py`) — pre-bakes the world_map API via a Flask test client + fetch interceptor.
2. **WorldExplorer** (`world_explorer/`) — fast-cold-start interactive file browser, lazy HDF5 backend.
3. **Combined live map + explorer** — aspirational, no code yet.

Today the two apps run on **two divergent data backends**:
- **WorldMap**: eager — `world_map/core/world_loader.py` builds the full in-memory object graph (`Person`/`Venue`/`Subset` + managers, `WorldData`). Cold start ~48.8s (medieval).
- **WorldExplorer**: lazy — `world_explorer/explorer_world_loader.py` (`ExplorerWorld`: geography + aggregate `UnitStats` + row indices) + `explorer_loader.py` (`ExplorerLoader`: on-demand HDF5 reads). Cold start ~1.7s.

ADR 0001 accepted this split as "two apps, genuinely different needs." **Inspection shows that premise is mostly false.** Reading the world_map routes:
- `/api/geography/<level>` and `/api/geography/unit/<name>` use only `world.geography` + `world._unit_statistics` — **both resident in `ExplorerWorld` already** (`world_map/routes/geography.py:35-134`).
- `/api/geography/unit/<name>/people`, `/api/venues/venue/<id>`, `/api/population/person/<id>` each have a **direct lazy equivalent** in `ExplorerLoader` (`load_unit_people`, `load_venue_detail`, `load_person_slim`+`load_person_activities`).
- `/api/venues/<venue_type>` (the venue map layer, `world_map/routes/venues.py:35-86`) is the only endpoint needing **all** venue rows — but as a **bulk array read**, not Python objects.

So the eager object model exists almost entirely to serve things the lazy backend already does. The dominant cold-start cost is **not** the object loops (~9.5s) but the **activity-map `np.unique`** in `_compute_slim_statistics` / `_compute_unit_statistics` (~tens of seconds). WorldExplorer is fast because it skips activity stats; WorldMap's landing page displays them, so it can't.

**Decision (from grilling):**
- **One backend, retire the eager model.** Migrate WorldMap onto the lazy array/index backend. Keep two apps; share one backend.
- **Remove activity statistics from WorldMap's landing page.** Defer them to a future on-demand "Statistics" button (live server computes per-`GeoUnit`; static export always bakes them). This is the unlock: with activity stats gone from cold start, WorldMap gets the *same* fast start as the explorer — no upstream HDF5 changes needed now.
- **Output 3: enable only**, don't build it here.
- **Frontend: out of scope** (the ~2,500 lines of parallel JS stay; only the small activity-stats display removal in PR5).
- Outcome: one data path → fixes WorldMap cold start, deletes a whole duplicate backend, and makes output 3 nearly free later.

**Intended deliverable:** a sequence of independent, hand-off-able PRs, each leaving tests green.

## Target architecture

A single lazy backend in a **neutral top-level package `world_reader/`** that depends on **neither** app, so both `world_map` and `world_explorer` depend on it (no cycles). Because `world_reader` cannot import from `world_map`, the app-agnostic primitives the backend needs move into it too (see PR1).

Final shape (names reached incrementally — move first, rename last, per decision below):

- **`WorldStore`** (currently `ExplorerWorld`) — resident: `geography` tree, per-unit `UnitStats`, `SubtreeIndex`, locate indices. Holds no `Person`/`Venue`/`Subset` objects.
- **`RecordReader`** (currently `ExplorerLoader`) — all on-demand HDF5 reads. Final constructor `(hdf5_path, store)`, not 16 loose args.
- **`SubtreeIndex`** — unchanged (DFS pre-order interval index).
- **`build_world_store`** (currently `load_explorer_world`).
- One **`compute_unit_statistics(..., include_activity_counts: bool)`** replacing the ~80%-identical `_compute_unit_statistics` / `_compute_explorer_unit_statistics`.

Both apps become thin (factory + context + routes + frontend) over `world_reader`.

**Resolved decisions:** (1) neutral top-level `world_reader/` package; (2) **move first, rename later** — PR3 relocates keeping `ExplorerWorld`/`ExplorerLoader` names; the rename + constructor deepening is its own late PR (PR8); (3) app-assembly cleanup (PR9) is in-scope for this series; (4) PR5 carries a note to investigate the static-export activity-stats path.

## PR series

Ordered lowest-risk-first; each is independently reviewable and behaviour-preserving unless noted.

### PR1 — Create `world_reader/`; move app-agnostic primitives in (safe)
Create the neutral package and relocate the shared, app-agnostic foundation the backend needs (so `world_reader` imports nothing app-specific):
- `_load_geography` + `GeoUnit` + `GeographyManager` (from `world_map/core/world_loader.py` + `world_data.py`).
- `UnitStats`, `AGE_LABELS`, `AGE_BREAKS` (from `world_data.py`).
- `pagination` (`calc_total_pages`, `paginate`, `PaginationSlice`).
- One consolidated numpy→python converter + `SEX_DECODE`, collapsing `_convert_numpy_value` (`world_loader.py:25`), `convert_numpy_types` (`utils.py:4`), `_decode` (`explorer_loader.py:450`), and the duplicated `_SEX_DECODE` (`world_loader.py:549`, `explorer_loader.py:8`).
Rewire `world_map` + `world_explorer` imports (keep thin re-export shims where it reduces churn). The eager-only classes (`Person`/`Venue`/`Subset`/`WorldData`/managers) stay in `world_map` for now.
- Tests: extend `tests/test_utils.py`; full suite green. Risk: low-medium (move + import rewire).

### PR2 — Unify unit-statistics computation (safe)
Extract one `world_reader.compute_unit_statistics(f, geography, *, include_activity_counts)`; have both loaders call it (world_map `True`, explorer `False`). Removes the duplicated leaf-stats + `_add`/`_aggregate` logic.
- Tests: `tests/test_unit_stats.py`, `tests/test_geography.py` guard behaviour. Risk: low-medium.

### PR3 — Move the lazy backend into `world_reader` (structural keystone, pure move)
Relocate `ExplorerWorld`, `ExplorerLoader`, `SubtreeIndex`, `load_explorer_world` from `world_explorer/` into `world_reader/` — **keeping current names** (rename deferred to PR8). Rewire `world_explorer` imports + factory. No signature changes.
- Tests: full `tests/test_explorer_*` suite must pass unchanged. Risk: medium (mechanical import churn).

### PR4 — Add bulk-venue read for the map venue layer
Add `ExplorerLoader.load_venues_by_type(venue_type)` (and any bulk read the map layer needs) returning GeoJSON-ready rows (coords + member counts) via array reads, replacing the `world.venues.get_venues_by_type` iteration in `world_map/routes/venues.py:43-74`.
- Tests: new bulk-venue read test against a fixture HDF5. Risk: medium (new code, well-scoped).

### PR5 — Remove activity statistics from WorldMap landing page (behaviour change — intentional)
- Backend: stop computing/returning activity stats on the WorldMap cold-start path — `include_activity_counts=False`, drop the activity portion of `_compute_slim_statistics` from `/api/world/statistics` (`world_map/routes/venues.py:166-181`).
- Frontend (small, unavoidable): remove the activity-stats display block from the world_map landing stats in `world_map/static/js/app.js`.
- Create **`docs/handoff/activity-stats-on-demand.md`** from the "Handoff — future" section below.
- **Note for implementer:** before finalising, determine whether `export_static` currently bakes **unit-level** activity stats or only **world-level** (read `export_static._collect_data` / `_collect_events_data`). Document the finding in the handoff doc and adjust the export-path design accordingly (the static export must always show stats).
- Risk: medium. This is the unlock that lets WorldMap go fast on the lazy backend.

### PR6 — Migrate WorldMap onto the `world_reader` backend (high risk — split)
Written against the current `ExplorerWorld`/`ExplorerLoader` names (PR8 renames afterwards).
**PR6a:** Rewrite `world_map/app.py:create_app` to build `ExplorerWorld` + `ExplorerLoader` instead of eager `WorldData`. Rewrite `AppContext` (`world_map/context.py`) to carry the store + loader (+ `projection`, `map_config`, `app_config`; `venue_index`→derived/removed). Rewrite `routes/geography.py` (unit detail, unit people→`load_unit_people`) and the single-record routes `routes/venues.py:89` (`load_venue_detail`), `routes/population.py:43` (`load_person_slim`+`load_person_activities`). Update `launch_world_map.py` + `export_static.py:644-653,812` world-load path.
**PR6b:** Rewrite the venue map layer `routes/venues.py:35-86` (→`load_venues_by_type`) and `routes/population.py:15` / `routes/venues.py:166` aggregate-stats endpoints to read from the store's `_unit_statistics` / bulk reads.
- Contract: API responses must stay byte-compatible (static export + frontend depend on them). Drive with the test client like `export_static._collect_data`.
- Tests: `tests/test_geography.py`, `tests/test_pagination.py`, plus a golden-JSON check on the static-export endpoints. Risk: high — most care here.

### PR7 — Delete the eager object model (deletion test)
Once nothing references them, delete the `WorldData` managers, `Person`/`Venue`/`Subset` objects, `_load_population`/`_load_venues`/`_load_subsets`, and the eager `load_world_from_hdf5` path in `world_map/core/world_loader.py` + `world_data.py`.
- Add **ADR 0002** (unified lazy backend, supersedes 0001); mark ADR 0001 `Superseded by 0002`. Update `CONTEXT.md`: note WorldMap no longer materialises `Person`/`Venue`/`Subset`.
- Risk: low once PR6 lands (pure deletion); large locality win.

### PR8 — Rename + deepen the backend seam
Now both apps depend on `world_reader`, do the deferred rename and seam fix in one pass: `ExplorerWorld→WorldStore`, `ExplorerLoader→RecordReader`, `load_explorer_world→build_world_store`. **Collapse `RecordReader`'s 16-arg constructor to `(hdf5_path, store)`** — reach into `store` for the indices (removes the wide seam at the old `world_explorer/app.py:27-44`).
- Update `CONTEXT.md` with `WorldStore`/`RecordReader`. Tests: full suite green. Risk: medium (rename churn + one signature change).

### PR9 — Unify app-assembly boilerplate
Extract the shared `create_app` skeleton (Flask+CORS+context-stash+error handlers), unify `theme.css` serving (`config_routes.py:48` vs `explorer.py:28`), make pagination invocation consistent (both via `paginate`/`calc_total_pages`).
- Risk: medium. Polish that pays off once output 3 is built later.

## Handoff — future: on-demand activity statistics

To be saved as `docs/handoff/activity-stats-on-demand.md` in PR5.

**Goal:** WorldMap landing loads fast (no activity `np.unique` at startup). Activity stats served on demand.

**Live server:** new endpoint e.g. `GET /api/geography/unit/<name>/activity-stats`. Computes the activity-map `np.unique` scoped to that unit's subtree using `SubtreeIndex.person_rows(unit_id)` → activity-map offsets, far cheaper than whole-world. Cache per-unit (in-memory). Frontend: a "Statistics" button in the detail panel triggers the fetch + renders.

**Static export:** pre-bake activity stats for all units (or top N levels) during `export_static`; bundle into `window.STATIC_WORLD_DATA`; the fetch interceptor serves them so the exported map always shows stats.

**Open:** granularity (per-leaf vs aggregated-upward), cache eviction policy, whether to also expose world-level activity stats.

## Verification

- After each PR: `pytest` green (`tests/`).
- PR3/PR6: run both apps end-to-end — `python launch_world_explorer.py` (port 5001) and `python launch_world_map.py` (port 5000) against a real `world_state.h5`; click through tree, venue detail, person detail, paginated lists.
- PR6: golden-JSON diff on the static-export endpoints (drive `create_app(...).test_client()` over `/api/map/config`, `/api/geography/*`, `/api/venues/*`, `/api/population/person/<id>`) before vs after — responses must match.
- PR5/PR6: measure WorldMap cold start before/after (expect drop from ~tens-of-seconds to ~1-2s on medieval).
- PR4: verify the venue map layer renders the same marker set as before.

## Out of scope (deferred)

- **Output 3** (combined live map+explorer) — enabled by the unified backend, built later.
- **Frontend JS unification** (~2,500 parallel lines) — untouched here except PR5's small activity-stats display removal.

## Decisions (resolved)

1. Neutral top-level package `world_reader/`.
2. Move first (PR3), rename + seam-deepen later (PR8).
3. App-assembly cleanup (PR9) in-scope.
4. Static-export activity-stats path: investigated and documented in PR5.

## Conventions for all PRs

- **Base branch:** `master`. Each PR stacks on the previous one's branch (PR2 branches off PR1's branch, etc.). State the base explicitly in the PR description.
- **Branch name:** `refactor/NN-slug` (e.g. `refactor/01-world-reader-package`).
- **Baseline:** `pytest -q` is green at `master` HEAD (50 passed). Keep it green.
- **Conda env:** tests run under the `graphify` conda env (`/home/gavin/.conda/envs/graphify/bin/pytest`).
- **Commits:** UK English, concise. Do not add AI attribution or reference plan/handoff files in commit messages.
- **Do not commit** `graphify-out/` (analysis artefacts) or the loose untracked SVG/`docs/world_explorer.md` files already in the tree — add only the files your PR touches.

---
name: world-visualiser-context
description: Domain glossary for the may_world_visualiser repository
---

# Domain Glossary

## Core Domain Objects

**GeoUnit**
A geographical unit loaded from the HDF5 world file. GeoUnits form a strict hierarchy via `.parent` / `.children` references. Each GeoUnit has a named level (e.g. `country`, `region`, `area`). Venues may be directly assigned to **any** GeoUnit, leaf or non-leaf (e.g. commercial/leisure venues commonly sit at MGU level above the SGU/household units that hold the resident population). Population is leaf-only: only leaf GeoUnits directly contain People. Every GeoUnit aggregates statistics upward from its own direct assignments plus its descendants.

**Person**
An individual resident assigned to exactly one GeoUnit. Carries slim attributes: id, age, sex. Full detail (activity_map, including activities) is available via a separate API call.

**Venue**
A location assigned to a GeoUnit, of a named VenueType. Contains zero or more Subsets. A Venue whose `parent_id == -1` and that has at least one ChildVenue is a **ParentVenue**; it appears at the top level of the venue list and shows a child count and amalgamated member total. A Venue whose `parent_id != -1` is a **ChildVenue**; it never appears at the top level and is accessible only by expanding its ParentVenue. The hierarchy is two levels deep: ChildVenues do not themselves have children.

**Subset**
A named membership group within a Venue (e.g. a household within a building). In the Venue list, only a member count is shown. Full member detail (id, age, sex, geo_unit) is loaded on demand when a Venue is opened in the Detail Panel.

**CalendarEvent**
A scheduled occurrence at a Venue, read from an external CSV (`calendar_events_named.csv`). Each row carries an `event_name`, `date`, and `duration_days`, and is keyed by `(hosting_geo_unit_id, venue_type_name)` — not by a direct venue ID. CalendarEvents are optional (require an explicit `--calendar-events` flag at launch); if absent, no Calendar Events section appears in the Detail Panel. The design is general: any `venue_type_name` value can appear in the CSV; currently only `fair` rows are loaded.

**ActivityMap**
The full set of activities for a single Person, loaded on demand in the Detail Panel. Each entry records the activity type, the Venue where it takes place, the Subset within that Venue, and the Venue's GeoUnit. The slim Person object carries no activity data at all; the ActivityMap is the sole source of a Person's activities, loaded on demand.

**VenueType**
A string label classifying Venues (e.g. `household`, `school`, `workplace`). The set of types is world-specific and read from the HDF5 registry.

**UnitStats**
Pre-computed aggregate statistics for a GeoUnit: total population, age distribution, sex distribution, venue counts by VenueType, and activity counts. Aggregated upward through the hierarchy at load time.

## Applications

**WorldMap** (`world_map/`)
Interactive map-based visualisation of a world file. Renders GeoUnits and Venues on a geographic map with event overlays. Flask app; launched via `launch_world_map.py`. Clicking a GeoUnit marker opens its info panel; from there, Venues and People are separate lazy-loaded sections (fetched only when opened, never on the unit click itself), and opening a single Venue or Person swaps the panel into a Detail Panel view in place (back button returns to the unit view) — the same domain object and Detail Panel as WorldExplorer's, but WorldMap shows it as one panel that swaps content rather than two panes side by side.

**WorldExplorer** (`world_explorer/`)
File-explorer-style browser interface for inspecting a world file. Left pane shows the GeoUnit hierarchy as a collapsible tree. Right pane shows UnitStats, a paginated Venue list (grouped by VenueType, inline-expandable), and a paginated People list (inline-expandable slim detail). Both Venues and People have a "View full details" button that opens the Detail Panel. Flask app; launched via `launch_world_explorer.py` on port 5001.

Both WorldMap and WorldExplorer run on the same shared lazy backend in `world_reader/` (`WorldStore` + `RecordReader`): neither materialises Person, Venue or Subset as in-memory objects. Only the GeoUnit hierarchy and aggregate UnitStats are held resident; individual Person/Venue/Subset records are served on demand from HDF5.

Pagination follows two intentional patterns: routes/tests holding a fully materialised list use `paginate`/`PaginationSlice` (`world_reader/pagination.py`); `RecordReader` hand-slices numpy arrays/HDF5 datasets directly (reusing only `calc_total_pages`) so it never has to materialise a full array just to re-slice it.

**Detail Panel**
Displays full detail for a single domain object (Person or Venue). For a Person: id, age, sex, geo_unit, properties, and activity map. For a Venue: name, type, geo_unit, coordinates, properties, and member list (paginated by Subset). In WorldExplorer it's a slide-in panel on the right edge, alongside the unit detail pane, with back/forward history. In WorldMap it's the same content rendered inside the existing GeoUnit info panel as a swapped-in view (back button, no second panel). Both apps' Detail Panel includes a "go to geo unit" action that jumps to the object's owning GeoUnit — in WorldMap this also flies the map to that GeoUnit's coordinates.

## Testing Conventions

Python tests under `tests/` mirror the three packages above:

- `tests/world_reader/` — the shared lazy backend (WorldStore, RecordReader, statistics, ID-index/venue-ID semantics).
- `tests/world_map/` — WorldMap Flask routes, config, pagination, conversion utilities.
- `tests/world_explorer/` — WorldExplorer Flask routes.
- `tests/support/world_builder.py` — shared `WorldBuilder` fixture factory; writes a synthetic `world_state.h5` and loads it via the real `build_world_store`/`RecordReader` path so tests exercise the same backend as production.
- `tests/conftest.py` — root-level `client_for` fixture (Flask test client from an `AppContext`), available to all subdirectories.
- `tests/js/` — Jest tests for `world_map/static/js/` ES modules; standalone, no shared fixtures.

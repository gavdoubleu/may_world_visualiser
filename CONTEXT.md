---
name: world-visualiser-context
description: Domain glossary for the may_world_visualiser repository
---

# Domain Glossary

## Core Domain Objects

**GeoUnit**
A geographical unit loaded from the HDF5 world file. GeoUnits form a strict hierarchy via `.parent` / `.children` references. Each GeoUnit has a named level (e.g. `country`, `region`, `area`). Leaf GeoUnits directly contain People and Venues; non-leaf GeoUnits aggregate statistics upward from their descendants.

**Person**
An individual resident assigned to exactly one GeoUnit. Carries slim attributes: id, age, sex, and a list of activity type strings. Full detail (activity_map) is available via a separate API call.

**Venue**
A location assigned to a GeoUnit, of a named VenueType. Contains zero or more Subsets.

**Subset**
A named membership group within a Venue (e.g. a household within a building). Carries a member count (slim mode only — individual member ids are not loaded). Full member detail (id, age, sex, geo_unit) is loaded on demand via the venue-members API.

**VenueType**
A string label classifying Venues (e.g. `household`, `school`, `workplace`). The set of types is world-specific and read from the HDF5 registry.

**UnitStats**
Pre-computed aggregate statistics for a GeoUnit: total population, age distribution, sex distribution, venue counts by VenueType, and activity counts. Aggregated upward through the hierarchy at load time.

## Applications

**WorldMap** (`world_map/`)
Interactive map-based visualisation of a world file. Renders GeoUnits and Venues on a geographic map with event overlays. Flask app; launched via `launch_world_map.py`.

**WorldExplorer** (`world_explorer/`)
File-explorer-style browser interface for inspecting a world file. Left pane shows the GeoUnit hierarchy as a collapsible tree. Right pane shows UnitStats, a paginated Venue list (grouped by VenueType, inline-expandable), and a paginated People list (inline-expandable slim detail, with a slide-in panel for full Person detail). Flask app; launched via `launch_world_explorer.py` on port 5001. Imports loaders and data classes from `world_map.core`.

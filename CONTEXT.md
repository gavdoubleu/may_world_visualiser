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
A named membership group within a Venue (e.g. a household within a building). In the Venue list, only a member count is shown. Full member detail (id, age, sex, geo_unit) is loaded on demand when a Venue is opened in the Detail Panel.

**ActivityMap**
The full set of activities for a single Person, loaded on demand in the Detail Panel. Each entry records the activity type, the Venue where it takes place, the Subset within that Venue, and the Venue's GeoUnit. The slim Person object carries only a list of activity type strings; the ActivityMap is the on-demand expansion.

**VenueType**
A string label classifying Venues (e.g. `household`, `school`, `workplace`). The set of types is world-specific and read from the HDF5 registry.

**UnitStats**
Pre-computed aggregate statistics for a GeoUnit: total population, age distribution, sex distribution, venue counts by VenueType, and activity counts. Aggregated upward through the hierarchy at load time.

## Applications

**WorldMap** (`world_map/`)
Interactive map-based visualisation of a world file. Renders GeoUnits and Venues on a geographic map with event overlays. Flask app; launched via `launch_world_map.py`.

**WorldExplorer** (`world_explorer/`)
File-explorer-style browser interface for inspecting a world file. Left pane shows the GeoUnit hierarchy as a collapsible tree. Right pane shows UnitStats, a paginated Venue list (grouped by VenueType, inline-expandable), and a paginated People list (inline-expandable slim detail). Both Venues and People have a "View full details" button that opens the Detail Panel. Flask app; launched via `launch_world_explorer.py` on port 5001. Imports loaders and data classes from `world_map.core`.

**Detail Panel**
The slide-in panel on the right edge of WorldExplorer. Displays full detail for a single domain object (Person or Venue). For a Person: id, age, sex, geo_unit, properties, and activity map. For a Venue: name, type, geo_unit, coordinates, properties, and member list (paginated by Subset). Panel history supports back/forward navigation.

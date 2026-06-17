# Plan: WorldMap explorer-style detail panel

> Source PRD: `tmp/prds/worldmap-explorer-detail-panel.md`

## Architectural decisions

- **Routes**: new Flask blueprint (separate file from `geography.py`/`venues.py`/`population.py`), thin wrappers over existing `world_reader.RecordReader` methods:
  - `GET /api/geography/unit/<unit_name>/venues?type=&page=&per_page=`
  - `GET /api/geography/venue/<venue_id>/detail`
  - `GET /api/geography/venue/<venue_id>/members?subset=&page=&per_page=`
  - `GET /api/geography/venue/<venue_id>/children?page=&per_page=`
  - `GET /api/geography/venue/<venue_id>/locate`
  - `GET /api/geography/person/<person_id>/locate`
  - Reused unchanged: `/api/geography/unit/<unit_name>/people`, `/api/population/person/<id>`
- **Panel model**: single floating panel, swaps content in place (no second panel).
- **PanelNavigator**: new DOM-free pure module with `push(view)`/`pop()`/`current()`; every view transition pushes, back always pops — this is the only mechanism for "back", replacing per-view hardcoded back targets.
- **Not config-driven**: Venues/People/Detail Panel are hardcoded views, not `app_config.panel.detail_sections` entries (ADR 0003).
- **Pagination default**: 20/page everywhere new.
- **Theming**: existing WorldMap `--theme-*` CSS vars only.
- **No cross-app code sharing**: logic ported/adapted into WorldMap's own files, not extracted to a shared module.

---

## Phase 1: PanelNavigator + wire up People

**User stories**: 4, 5, 9, 13

### What to build
Build the PanelNavigator module (push/pop/current, pure state, no DOM). Retrofit it onto the existing-but-unwired `people.js`: add a "View People" entry point on the unit panel, route its People-list/Person-detail/back transitions through PanelNavigator instead of the current hardcoded back-target callback.

### Acceptance criteria
- [ ] PanelNavigator unit-tested: push/pop/current, including a multi-level stack.
- [ ] Clicking a unit's "View People" button fetches and shows the paginated People list (lazy, not fetched on unit click).
- [ ] Clicking a Person shows their Detail view (age/sex/geo_unit/properties/activity map); back returns to the People list; back again returns to the unit view.

---

## Phase 2: Venues list section

**User stories**: 2, 3

### What to build
New backend route for unit-scoped paginated venues, filterable by type. New "Venues" entry point on the unit panel showing venues grouped by VenueType, each group paginated, pushed via PanelNavigator.

### Acceptance criteria
- [ ] Route returns paginated venues for a unit, optionally filtered by `type`, 404 on unknown unit.
- [ ] "View Venues" entry point fetches lazily (not on unit click).
- [ ] Venues render grouped by type with per-group pagination.

---

## Phase 3: Venue Detail view

**User stories**: 6, 7

### What to build
New routes for venue detail and paginated subset members (filterable by subset). Venue Detail view rendering name/type/geo_unit/coordinates/properties, with Subsets shown as member counts that expand (on demand) into paginated member lists.

### Acceptance criteria
- [ ] Venue detail route 404s on unknown id, returns full shape otherwise.
- [ ] Members route paginates correctly and supports filtering by subset.
- [ ] Clicking a Venue from the Venues list pushes its Detail view via PanelNavigator; back returns to the Venues list at the correct scroll/page state.
- [ ] Expanding a Subset fetches its members only on expand.

---

## Phase 4: ParentVenue/ChildVenue browsing

**User stories**: 8

### What to build
New route for paginated venue children. Venue Detail view gains a paginated ChildVenue list when the venue is a ParentVenue (has children); clicking a ChildVenue pushes its own Detail view.

### Acceptance criteria
- [ ] Children route paginates correctly, empty list for a leaf/ChildVenue.
- [ ] ParentVenue Detail view shows paginated ChildVenue list; ChildVenue Detail view does not show a children section.
- [ ] Clicking a ChildVenue pushes its Detail view via PanelNavigator; back returns to the parent's Detail view.

---

## Phase 5: Go-to-geo-unit cross-nav

**User stories**: 11, 12, 14

### What to build
New locate-venue and locate-person routes resolving the owning GeoUnit. "Go to geo unit" icon (copied from WorldExplorer assets) in both Venue Detail and Person Detail views: on click, flies the Leaflet map to that GeoUnit's coordinates and pushes that GeoUnit's own unit view via PanelNavigator.

### Acceptance criteria
- [ ] Both locate routes 404 on unknown id, otherwise return the owning GeoUnit's identity/coordinates.
- [ ] Clicking the icon from a Venue or Person Detail view flies the map and swaps the panel to that unit's view in one action.
- [ ] No other panel interaction moves the map.

---

## Phase 6: Activity-map → Venue cross-link

**User stories**: 10

### What to build
Each activity-map entry in a Person's Detail view (naming a Venue) becomes a link that pushes that Venue's Detail view via PanelNavigator.

### Acceptance criteria
- [ ] Clicking an activity-map entry opens the correct Venue's Detail view.
- [ ] Back from that Venue Detail view returns to the originating Person's Detail view (not to a Venues list) — proves PanelNavigator's stack handles cross-navigation correctly.

---

## Phase 7: Cleanup + theming pass

**User stories**: 15, 16, 17, 18

### What to build
Remove the old eager `venue_types` breakdown and `venue_details` list sections from the panel config/default config. Verify every new view renders correctly under dark/light/accessible_dark/accessible_light themes. Confirm all new pagination defaults to 20/page. Confirm new routes live in their own file, not `geography.py`/`venues.py`.

### Acceptance criteria
- [ ] `venue_types`/`venue_details` no longer appear on the unit panel; Venues/People are the only venue/people browsing entry points.
- [ ] Manual check: new panel content legible and correctly styled under all four themes.
- [ ] All new paginated endpoints default to `per_page=20` when unspecified.

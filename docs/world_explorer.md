# WorldExplorer

File-explorer-style browser for inspecting a `world_state.h5` file. Launched independently of WorldMap on port 5001.

## Architecture

WorldExplorer uses a **lazy HDF5 backend** — it never materialises Person, Venue, or Subset as in-memory Python objects. Only the geography tree, aggregate per-unit statistics, and lightweight row indices are held in memory. Individual records are read from HDF5 on demand per request. This reduces cold-start time from ~49s to ~1.7s on the medieval dataset (see ADR 0002).

The lazy backend (`WorldStore`/`RecordReader`/`SubtreeIndex`/`build_world_store`) lives in
the neutral `world_reader/` package and is shared with WorldMap — neither app
materialises Person/Venue/Subset as resident objects. WorldExplorer itself is
just the thin Flask factory, context and blueprint:

```
launch_world_explorer.py
└── world_explorer/
    ├── app.py             # Flask factory: create_app(world, hdf5_path)
    ├── context.py         # ExplorerContext dataclass + get_explorer_context()
    └── routes/
        └── explorer.py    # explorer_bp blueprint: all API and UI routes

world_reader/
├── world_store.py         # build_world_store() → WorldStore; SubtreeIndex
└── record_reader.py       # RecordReader: on-demand HDF5 reads
```

## Key Classes

### `WorldStore`
Holds what is resident in memory:
- `geography` — GeoUnit hierarchy
- `_unit_statistics` — per-unit population / age / sex / venue-type counts, aggregated upward
- `person_id_to_idx` — maps person ID → HDF5 array row
- `subset_venue_ids` — sorted venue IDs for binary-search subset lookup
- `subtree_index` — `SubtreeIndex` for O(1) subtree row ranges
- `population`, `venues` — always `None` (objects not materialised)

### `SubtreeIndex`
Built from a DFS pre-order traversal of the geography tree. Population and venue rows are sorted by their unit's pre-order value, so every unit's whole subtree forms a contiguous slice. Subtree People/Venue lists paginate in O(1) without loading objects.

### `RecordReader`
All per-request HDF5 reads, constructed as `RecordReader(hdf5_path, store)` —
reaches into the `WorldStore` for its index arrays. Opens the file, reads the
required rows, closes. Methods:

| Method | Returns |
|--------|---------|
| `load_person_slim(person_id)` | `{id, age, sex, geo_unit, properties}` |
| `load_person_activities(person_id)` | `[{activity_name, venue_id, venue_name, venue_type, venue_geo_unit, subset_name}]` |
| `load_venue_detail(venue_id)` | `{id, name, type, geo_unit, coordinates, subsets}` |
| `load_venue_members(venue_id, page, per_page, subset_filter)` | paginated subset member lists |
| `load_unit_people(unit_name, page, per_page)` | paginated people for unit's subtree |
| `load_unit_venues(unit_name, page, per_page, type_filter)` | paginated venues for unit's subtree |

## API Endpoints

All routes are under the `explorer_bp` blueprint.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Main SPA (index.html) |
| `GET` | `/theme.css` | Dynamic CSS from `dark_scientific` theme YAML |
| `GET` | `/api/explorer/tree` | Full GeoUnit tree with population and venue counts |
| `GET` | `/api/explorer/unit/<name>` | Unit detail: stats, parent, children |
| `GET` | `/api/explorer/unit/<name>/people` | Paginated people for unit's subtree (`?page`, `?per_page`) |
| `GET` | `/api/explorer/unit/<name>/venues` | Paginated venues for unit's subtree (`?page`, `?per_page`, `?type`) |
| `GET` | `/api/explorer/person/<id>` | Slim person detail (no activities) |
| `GET` | `/api/explorer/person/<id>/full` | Person's full activity map |
| `GET` | `/api/explorer/venue/<id>/detail` | Venue detail with subset summary |
| `GET` | `/api/explorer/venue/<id>/members` | Paginated subset members (`?page`, `?per_page`, `?subset`) |

Pagination defaults: `page=1`, `per_page=50`, max `per_page=200`.

## Shared Components

WorldExplorer reuses:
- `world_reader.geography` — HDF5 geography tree loader (`load_geography`, `GeoUnit`, `GeographyManager`)
- `world_reader.UnitStats` — aggregate stats dataclass
- `world_reader.calc_total_pages` — pagination helper
- `world_map.themes.theme_css.build_root_block` — CSS variable generation
- `world_map.utils.convert_numpy_types` — JSON serialisation helper

It does **not** use WorldMap's `AppContext`, population/venues/events blueprints, or `load_world_from_hdf5`.

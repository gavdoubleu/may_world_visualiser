# may_world_visualiser

Three tools for visualising and inspecting world files (`.h5`) produced by the [MAY](https://github.com/gavdoubleu/may) agent-based modelling software:

| Tool | Purpose |
|------|---------|
| **WorldMap** | Interactive geographic map — explore the spatial layout of a world, population overlays, and the spread of simulation events |
| **Static Export** | Share a self-contained HTML snapshot of a WorldMap — no installation required to view |
| **WorldExplorer** | File-browser interface — navigate the GeoUnit hierarchy, inspect population and venue data in detail |

See the **User Guide** for usage instructions, **Architecture** for the domain model and shared backend, and **API Reference** for auto-generated docstring documentation of `world_reader`, `world_map` and `world_explorer`.

## Requirements

Python 3.10+.

```bash
pip install -r requirements.txt
```

## Project layout

```
may_world_visualiser/
├── launch_world_map.py       # WorldMap entry point
├── launch_world_explorer.py  # WorldExplorer entry point
├── export_static.py          # static export entry point
├── requirements.txt
├── world_map/
│   └── yaml/                 # config files (config.yaml, themes, panels)
├── world_explorer/           # WorldExplorer package
├── world_reader/             # shared HDF5 backend
└── webapp_utilities/         # shared Flask helpers (theming, app factory)
```

# may_world_visualiser

Interactive Leaflet.js map for visualising geographic world-state data stored in HDF5 files. Supports a live Flask server or self-contained static HTML export.

## Features

- Geographic unit hierarchy with clickable detail panels
- Population and venue overlays
- Simulation event visualisation
- OpenStreetMap or custom image backgrounds
- Themed map styles
- Offline-capable static export (no server, no internet required to view)

## Requirements

```
pip install -r requirements.txt
```

Python 3.10+, dependencies: Flask, h5py, numpy, pandas, PyYAML, numba.

## Usage

### Live server

```bash
python launch_world_map.py --world-file data/world_state_medieval.h5
```

Open `http://127.0.0.1:5000` in a browser.

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--host` | `127.0.0.1` | Server host |
| `--port` | `5000` | Server port |
| `--map-background` | `osm` | `osm` or `image` |
| `--map-image` | — | Path/URL to background image (requires `--map-background image`) |
| `--map-bounds` | — | `"north,east,south,west"` for custom image |
| `--map-attribution` | — | Attribution text for custom image |
| `--events-file` | — | Path to `simulation_events.h5` |
| `--debug` | off | Flask debug mode |

### Static export

```bash
python export_static.py --world-file data/world_state_medieval.h5 --output map.html
```

Produces a single self-contained HTML file. Open by double-clicking.

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--map-background` | `osm` | `osm` or `image` |
| `--map-image` | — | Local image (base64-embedded) or URL |
| `--map-bounds` | — | `"north,east,south,west"` |
| `--events-file` | — | Path to `simulation_events.h5` |
| `--cdn` | off | Load Leaflet from CDN instead of embedding |
| `--max-size-mb` | `80` | Max embedded world data size |
| `--events-max-size-mb` | `50` | Max embedded events data size |

### Custom image background example

```bash
python launch_world_map.py --world-file data/world_state_medieval.h5 \
    --map-background image \
    --map-image medieval_map.png \
    --map-bounds "56.0,2.0,49.5,-6.0" \
    --map-attribution "Medieval England 1348 AD"
```

## WorldExplorer

File-explorer browser for inspecting a world file. Uses a lazy HDF5 backend — only the geography tree and aggregate statistics are held in memory; People/Venues/Subsets are loaded on demand. Cold-start: ~1.7s (vs ~49s for WorldMap on the medieval dataset).

```bash
python launch_world_explorer.py --world-file data/world_state_medieval.h5
```

Open `http://127.0.0.1:5001` in a browser.

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--host` | `127.0.0.1` | Server host |
| `--port` | `5001` | Server port |
| `--debug` | off | Flask debug mode |

See [`docs/world_explorer.md`](docs/world_explorer.md) for full architecture and API reference.

## Project layout

```
may_world_visualiser/
├── launch_world_map.py      # WorldMap live server entry point
├── launch_world_explorer.py # WorldExplorer live server entry point
├── export_static.py         # static export entry point
├── *.sh                     # convenience shell scripts
├── requirements.txt
├── docs/
│   ├── adr/                 # architecture decision records
│   └── world_explorer.md    # WorldExplorer architecture + API reference
├── world_reader/            # shared lazy HDF5 backend (WorldStore, RecordReader)
│   ├── world_store.py       # build_world_store(), WorldStore, SubtreeIndex
│   ├── record_reader.py     # on-demand HDF5 reads (RecordReader)
│   ├── geography.py         # GeoUnit / GeographyManager / UnitStats
│   └── statistics.py        # compute_unit_statistics() and friends
├── world_map/               # WorldMap package (map-based visualisation)
│   ├── app.py               # Flask factory create_app()
│   ├── routes/              # Flask blueprints (geography, population, venues, events)
│   ├── events/              # event loading and analysis
│   ├── themes/              # CSS theme generation
│   └── yaml/                # config files (app_config, themes, panels, events)
└── world_explorer/          # WorldExplorer package (file-explorer browser)
    ├── app.py               # Flask factory create_app()
    ├── context.py           # ExplorerContext
    └── routes/              # explorer_bp blueprint
```

## Data format

World state is loaded from `.h5`/`.hdf5` files via `world_reader.build_world_store()`,
the single backend shared by WorldMap and WorldExplorer (see ADR 0002). Events are
loaded from a separate `simulation_events.h5`.

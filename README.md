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

## Project layout

```
may_world_visualiser/
├── launch_world_map.py     # live server entry point
├── export_static.py        # static export entry point
├── *.sh                    # convenience shell scripts
├── requirements.txt
└── world_map/              # importable package
    ├── app.py              # Flask factory create_app()
    ├── core/               # domain classes and HDF5 loader
    ├── routes/             # Flask blueprints (geography, population, venues, events)
    ├── events/             # event loading and analysis
    ├── themes/             # CSS theme generation
    └── yaml/               # config files (app_config, themes, panels, events)
```

## Data format

World state is loaded from `.h5`/`.hdf5` files via `world_map/core/world_loader.py`. Events are loaded from a separate `simulation_events.h5`.

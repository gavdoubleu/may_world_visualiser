# WorldMap & Static Export

## WorldMap

Visualise a world on an interactive map. Click regions to see population and venue summaries.

```bash
python launch_world_map.py --world-file data/my_world.h5
```

Open `http://127.0.0.1:5000` in a browser.

### Custom background image

By default WorldMap uses OpenStreetMap tiles. For historical or non-modern worlds where OSM would be anachronistic, use a custom image instead:

```bash
python launch_world_map.py --world-file data/my_world.h5 \
    --map-background image \
    --map-image path/to/map.png \
    --map-bounds "56.0,2.0,49.5,-6.0" \
    --map-attribution "Medieval England 1348 AD"
```

`--map-bounds` is `"north,east,south,west"` in decimal degrees.

### Simulation events

To overlay simulation events on the map, pass the events file:

```bash
python launch_world_map.py --world-file data/my_world.h5 --events-file data/simulation_events.h5
```

### Configuration

Optional settings (themes, panel layout, projection, geo-unit name overrides) are controlled via a YAML config file. The default config is `world_map/yaml/config.yaml`. See `world_map/yaml/CONFIG.md` for full documentation.

To use a custom config:

```bash
python launch_world_map.py --world-file data/my_world.h5 --config path/to/config.yaml
```

## Static Export

Produces a single self-contained `.html` file that can be opened in any browser — no Python, no server, no internet connection required. Useful for sharing a snapshot of a world with someone who has not installed this software.

```bash
python export_static.py --world-file data/my_world.h5 --output my_map.html
```

Supports the same `--map-background`, `--map-image`, `--map-bounds`, `--events-file`, and `--config` options as WorldMap.

!!! note
    Large world files may exceed the default size limit. Use `--max-size-mb` and `--events-max-size-mb` to increase it.

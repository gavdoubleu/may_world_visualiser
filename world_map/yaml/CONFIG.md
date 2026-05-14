# Configuration

All settings live in a single `config.yaml`. The default is `world_map/yaml/config.yaml`.

To use your own config, pass `--config /path/to/config.yaml` to either launcher:

```bash
python launch_world_map.py --world-file world.h5 --config /path/to/config.yaml
python export_static.py --world-file world.h5 --output map.html --config /path/to/config.yaml
```

---

## config.yaml structure

```yaml
theme: dark_scientific   # built-in name or path to a .yaml file (see below)

projection:
  type: web_mercator     # 'web_mercator' (default) or 'utm'
  # zone: 30            # required for utm

geo_unit_names:
  enabled: false
  csv_path: data/Geo_unit_names.csv   # relative to this config file
  id_column: MBD_Temp_ID
  name_column: Name

panel:
  # info panel layout — see config.yaml for full example

events:
  # event visualisation settings — see config.yaml for full example
```

`panel` and `events` are required. `projection` and `geo_unit_names` are optional.

---

## Themes

`theme:` accepts two formats:

- **Built-in name** (e.g. `dark_scientific`, `clean_minimal`) — looks in `world_map/yaml/themes/`
- **Path** (e.g. `./my_theme.yaml`) — resolved relative to your `config.yaml`

Built-in themes: `dark_scientific`, `clean_minimal`.

To create a custom theme, copy a built-in theme YAML and edit the colours/fonts.
Point `theme:` at it using a path relative to your `config.yaml`.

Theme file structure:

```yaml
title: "My World"
subtitle: null
logo_path: null   # relative to world_map/static/, or null to omit

colors:
  bg:             '#0f1117'
  surface:        '#111827'
  surface_raised: '#1e293b'
  border:         '#1e293b'
  text:           '#F9FAFB'
  text_muted:     '#cbd5e1'
  accent:         '#00d4ff'
  header_bg:      '#0d1117'
  header_text:    '#F9FAFB'
  header_gradient: 'linear-gradient(135deg, #0d1117 0%, #141d2e 100%)'
  header_border:   'rgba(0, 212, 255, 0.25)'
  header_shadow:   '0 1px 20px rgba(0, 212, 255, 0.08)'

fonts:
  display:      'IBM Plex Sans'
  display_file: 'ShareTechMono-Regular.woff2'   # in world_map/static/fonts/
  body:         'IBM Plex Sans'
  body_file:    'IBMPlexSans-Regular.woff2'
```

Font files must exist in `world_map/static/fonts/`.

---

## Map background and events file

These are CLI arguments, not config keys:

```bash
# Custom image background
python launch_world_map.py --world-file world.h5 \
    --map-background image \
    --map-image medieval_map.png \
    --map-bounds "56.0,2.0,49.5,-6.0" \
    --map-attribution "Medieval England 1348 AD"

# Events file
python launch_world_map.py --world-file world.h5 \
    --events-file simulation_events.h5
```

`--map-bounds` format: `"north,east,south,west"`. Omit `--map-background` for OpenStreetMap (default).

### UTM projection with a background image

Supply `--map-bounds` in WGS84 degrees corresponding to the image NW and SE pixel corners:

```python
from pyproj import Transformer
t = Transformer.from_crs("EPSG:<zone_epsg>", "EPSG:4326", always_xy=True)
lon_nw, lat_nw = t.transform(utm_x_min, utm_y_max)   # top-left pixel corner
lon_se, lat_se = t.transform(utm_x_max, utm_y_min)   # bottom-right pixel corner
# --map-bounds "lat_nw,lon_se,lat_se,lon_nw"
```
